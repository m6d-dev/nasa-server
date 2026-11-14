"""The 32-byte frame (BACKEND_TZ §3). Shared verbatim by backend, vdev and firmware.

Every field has its own "no data" sentinel; it decodes to `None`, never to 0
or a previous value.
"""

import binascii
import struct
from dataclasses import dataclass
from enum import IntEnum

FRAME = struct.Struct("<BBHIHHHhHHHBBBBHhH")
FRAME_SIZE = FRAME.size  # 32
FRAME_VERSION = 1

TYPE_SECOND = 1
TYPE_MINUTE = 2

FLAG_WORN = 1 << 0
FLAG_CHARGING = 1 << 1
FLAG_ECG_CONTACT = 1 << 2
FLAG_MOTION_ARTIFACT = 1 << 3
FLAG_TRAINING = 1 << 4
FLAG_HISTORY = 1 << 7  # replayed history: no /live, no LLM

U16_NONE = 0xFFFF
I16_NONE = 0x7FFF
U8_NONE = 0xFF

assert FRAME_SIZE == 32


class FrameReject(IntEnum):
    LENGTH = 1
    VERSION = 2
    CRC = 3
    TYPE = 4


def crc16_ccitt_false(data: bytes) -> int:
    # crc_hqx is poly 0x1021, non-reflected; init 0xFFFF makes it CCITT-FALSE
    # (check value for b"123456789" is 0x29B1). C speed matters for backfill.
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass(slots=True, frozen=True)
class Frame:
    type: int
    dev_id: int
    ts: int
    hr: float | None = None
    spo2: float | None = None
    rr: float | None = None
    skin_t: float | None = None
    co2_ppm: float | None = None
    press_hpa: float | None = None
    act_mg: float | None = None
    sqi: int = 0
    flags: int = 0
    batt_pct: int | None = None
    seq: int = 0
    hrv: float | None = None
    amb_t: float | None = None

    @property
    def worn(self) -> bool:
        return bool(self.flags & FLAG_WORN)

    @property
    def training(self) -> bool:
        return bool(self.flags & FLAG_TRAINING)

    @property
    def history(self) -> bool:
        return bool(self.flags & FLAG_HISTORY)


def _u16(v: int, scale: float) -> float | None:
    return None if v == U16_NONE else v / scale


def _i16(v: int, scale: float) -> float | None:
    return None if v == I16_NONE else v / scale


def decode(raw: bytes) -> Frame | FrameReject:
    if len(raw) != FRAME_SIZE:
        return FrameReject.LENGTH
    f = FRAME.unpack(raw)
    if f[0] != FRAME_VERSION:
        return FrameReject.VERSION
    if crc16_ccitt_false(raw[:30]) != f[17]:
        return FrameReject.CRC
    if f[1] not in (TYPE_SECOND, TYPE_MINUTE):
        return FrameReject.TYPE
    return Frame(
        type=f[1], dev_id=f[2], ts=f[3],
        hr=_u16(f[4], 10), spo2=_u16(f[5], 10), rr=_u16(f[6], 10),
        skin_t=_i16(f[7], 100), co2_ppm=_u16(f[8], 1), press_hpa=_u16(f[9], 10),
        act_mg=_u16(f[10], 1), sqi=f[11], flags=f[12],
        batt_pct=None if f[13] == U8_NONE else f[13], seq=f[14],
        hrv=_u16(f[15], 1), amb_t=_i16(f[16], 100),
    )


def _enc_u16(v: float | None, scale: float) -> int:
    return U16_NONE if v is None else max(0, min(U16_NONE - 1, round(v * scale)))


def _enc_i16(v: float | None, scale: float) -> int:
    return I16_NONE if v is None else max(-0x8000, min(I16_NONE - 1, round(v * scale)))


def encode(f: Frame) -> bytes:
    body = FRAME.pack(
        FRAME_VERSION, f.type, f.dev_id, f.ts,
        _enc_u16(f.hr, 10), _enc_u16(f.spo2, 10), _enc_u16(f.rr, 10),
        _enc_i16(f.skin_t, 100), _enc_u16(f.co2_ppm, 1), _enc_u16(f.press_hpa, 10),
        _enc_u16(f.act_mg, 1), f.sqi, f.flags,
        U8_NONE if f.batt_pct is None else f.batt_pct, f.seq & 0xFF,
        _enc_u16(f.hrv, 1), _enc_i16(f.amb_t, 100), 0,
    )
    crc = crc16_ccitt_false(body[:30])
    return body[:30] + struct.pack("<H", crc)
