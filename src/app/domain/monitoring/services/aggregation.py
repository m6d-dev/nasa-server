"""Seconds → minute (BACKEND_TZ §5.1)."""

from statistics import fmean, median

from src.app.domain.monitoring.constants.thresholds import MIN_VALID_SECONDS, SQI_VALID
from src.app.domain.monitoring.entities.minute import MinuteValues
from src.vigil_types.ingest.frame import TYPE_MINUTE, Frame

# optical channels: a second counts only with a good signal
_SQI_GATED = ("hr", "spo2", "rr", "hrv")
# contact / cabin sensors: sqi says nothing about them
_UNGATED = ("skin_t", "co2_ppm", "press_hpa", "amb_t")


def minute_of(ts: int) -> int:
    return ts - ts % 60


def fold_seconds(crew_id: int, minute_ts: int, frames: list[Frame]) -> MinuteValues:
    good = [f for f in frames if f.sqi >= SQI_VALID]
    vals: dict[str, float | None] = {}
    for m in _SQI_GATED:
        xs = [getattr(f, m) for f in good if getattr(f, m) is not None]
        vals[m] = median(xs) if len(xs) >= MIN_VALID_SECONDS else None
    for m in _UNGATED:
        xs = [getattr(f, m) for f in frames if getattr(f, m) is not None]
        vals[m] = median(xs) if len(xs) >= MIN_VALID_SECONDS else None
    acts = [f.act_mg for f in frames if f.act_mg is not None]
    n = len(frames)
    return MinuteValues(
        crew_id=crew_id,
        ts=minute_ts,
        act_mg=fmean(acts) if acts else None,
        sqi=fmean(f.sqi for f in frames) if n else None,
        worn_frac=sum(f.worn for f in frames) / n if n else 0.0,
        valid_s=sum(1 for f in good if f.hr is not None),
        training=sum(f.training for f in frames) * 2 > n,  # majority of seconds
        history=all(f.history for f in frames),
        kind=1,
        **vals,
    )


def from_minute_frame(crew_id: int, f: Frame) -> MinuteValues:
    """Type 2: the device already folded the minute; trust it (§7.2: always valid)."""
    return MinuteValues(
        crew_id=crew_id, ts=minute_of(f.ts),
        hr=f.hr, spo2=f.spo2, rr=f.rr, skin_t=f.skin_t, hrv=f.hrv,
        co2_ppm=f.co2_ppm, press_hpa=f.press_hpa, amb_t=f.amb_t,
        act_mg=f.act_mg, sqi=float(f.sqi),
        worn_frac=1.0 if f.worn else 0.0,
        valid_s=60 if f.hr is not None else 0,
        training=f.training, history=f.history, kind=TYPE_MINUTE,
    )


class MinuteAccumulator:
    """Buffers one device's seconds; a frame from the next minute closes the current one."""

    __slots__ = ("crew_id", "_minute", "_frames")

    def __init__(self, crew_id: int) -> None:
        self.crew_id = crew_id
        self._minute: int | None = None
        self._frames: list[Frame] = []

    def add(self, f: Frame) -> MinuteValues | None:
        m = minute_of(f.ts)
        closed = None
        if self._minute is not None and m != self._minute and self._frames:
            closed = fold_seconds(self.crew_id, self._minute, self._frames)
            self._frames = []
        self._minute = m
        self._frames.append(f)
        return closed

    def drop(self) -> None:
        self._minute, self._frames = None, []
