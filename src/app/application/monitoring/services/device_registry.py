"""Per-device link state and the frame acceptance rules (BACKEND_TZ §3)."""

import time
from collections import deque
from dataclasses import dataclass, field

from src.vigil_types.ingest.frame import Frame

# frame field -> metric code the frontend knows
FRAME_CHANNELS = {
    "hr": "hr", "spo2": "spo2", "rr": "rr", "skin_t": "skin_t", "hrv": "hrv",
    "co2_ppm": "ppco2", "press_hpa": "press", "amb_t": "amb_t",
}
LOSS_WINDOW_S = 3600


@dataclass(slots=True)
class DeviceState:
    dev_id: int
    crew_id: int
    last_ts: int | None = None
    last_seq: int | None = None
    last_rx_mono: float | None = None
    last_frame: Frame | None = None
    channels: set[str] = field(default_factory=set)
    worn_since_ts: int | None = None  # when it was taken off; None while worn
    received: int = 0
    lost: int = 0
    # (ts, frames received, frames lost) per accepted frame, for lost_pct_1h
    recent: deque[tuple[int, int]] = field(default_factory=deque)

    def accept(self, f: Frame) -> bool:
        if self.last_ts is not None and f.ts <= self.last_ts:
            return False  # duplicate or the past
        lost = 0
        if self.last_seq is not None:
            lost = (f.seq - self.last_seq - 1) % 256
        self.lost += lost
        self.received += 1
        self.recent.append((f.ts, lost))
        while self.recent and self.recent[0][0] <= f.ts - LOSS_WINDOW_S:
            self.recent.popleft()
        prev = self.last_frame
        if not f.worn and (prev is None or prev.worn):
            self.worn_since_ts = f.ts
        elif f.worn:
            self.worn_since_ts = None
        self.last_ts, self.last_seq, self.last_frame = f.ts, f.seq, f
        self.last_rx_mono = time.monotonic()
        for attr, code in FRAME_CHANNELS.items():
            if code not in self.channels and getattr(f, attr) is not None:
                self.channels.add(code)
        return True

    def link_age_s(self) -> float | None:
        return None if self.last_rx_mono is None else time.monotonic() - self.last_rx_mono

    def lost_pct_1h(self) -> float | None:
        if not self.recent:
            return None
        lost = sum(x[1] for x in self.recent)
        return round(100 * lost / (len(self.recent) + lost), 1)
