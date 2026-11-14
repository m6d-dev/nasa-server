from src.vigil_types.ingest.frame import (
    FLAG_WORN,
    FRAME_SIZE,
    TYPE_MINUTE,
    TYPE_SECOND,
    Frame,
    FrameReject,
    crc16_ccitt_false,
    decode,
    encode,
)


def test_crc_check_value():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_round_trip_keeps_values():
    f = Frame(type=TYPE_SECOND, dev_id=3, ts=1794650645, hr=62.4, spo2=97.1, rr=14.2, skin_t=33.57,
              co2_ppm=2600, press_hpa=1013.2, act_mg=12, sqi=92, flags=FLAG_WORN, batt_pct=86, seq=17,
              hrv=45, amb_t=22.41)
    raw = encode(f)
    assert len(raw) == FRAME_SIZE
    assert decode(raw) == f


def test_no_data_decodes_to_none():
    f = Frame(type=TYPE_MINUTE, dev_id=1, ts=60)
    g = decode(encode(f))
    assert isinstance(g, Frame)
    assert (g.hr, g.spo2, g.rr, g.skin_t, g.co2_ppm, g.press_hpa, g.batt_pct, g.hrv, g.amb_t) == (None,) * 9


def test_broken_crc_and_length_rejected():
    raw = bytearray(encode(Frame(type=TYPE_SECOND, dev_id=1, ts=1, hr=60)))
    raw[9] ^= 0xFF
    assert decode(bytes(raw)) is FrameReject.CRC
    assert decode(b"\x01" * 31) is FrameReject.LENGTH
