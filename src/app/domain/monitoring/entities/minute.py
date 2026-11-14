from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.app.domain.monitoring.constants.thresholds import (
    DEFAULT_PRESS_HPA,
    MMHG_PER_HPA,
)

# columns of agg_1m that carry a per-metric norm (BACKEND_TZ §10)
ROW_NORM_METRICS = ("hr", "spo2", "rr", "skin_t")


def ppco2_mmhg(co2_ppm: float | None, press_hpa: float | None) -> float | None:
    """§5.2. Missing pressure falls back to sea level, missing CO2 stays missing."""
    if co2_ppm is None:
        return None
    p = press_hpa if press_hpa is not None else DEFAULT_PRESS_HPA
    return co2_ppm * 1e-6 * p * MMHG_PER_HPA


@dataclass(slots=True)
class MinuteValues:
    """One closed minute, before any judgement. Input of `on_minute`."""

    crew_id: int
    ts: int  # start of the minute, unix seconds
    hr: float | None = None
    spo2: float | None = None
    rr: float | None = None
    skin_t: float | None = None
    hrv: float | None = None
    co2_ppm: float | None = None
    press_hpa: float | None = None
    amb_t: float | None = None
    act_mg: float | None = None
    sqi: float | None = None
    worn_frac: float = 0.0
    valid_s: int = 0
    training: bool = False
    history: bool = False
    kind: int = 1  # 1 = folded from seconds, 2 = minute frame

    @property
    def ppco2(self) -> float | None:
        return ppco2_mmhg(self.co2_ppm, self.press_hpa)

    def get(self, m: str) -> float | None:
        if m == "ppco2":
            return self.ppco2
        if m == "press":
            return self.press_hpa
        return getattr(self, m)


@dataclass(slots=True)
class MetricEval:
    z: float | None = None
    lo: float | None = None
    hi: float | None = None
    med: float | None = None
    learning: bool = True
    hard: int = 0  # level from hard limits
    base: int = 0  # level from the personal norm (after streaks)
    evaluated: bool = False  # took part in z-levels this minute


@dataclass(slots=True)
class MinuteResult:
    """A minute after the pipeline: what is written to agg_1m and shown."""

    v: MinuteValues
    ctx: int
    evals: dict[str, MetricEval] = field(default_factory=dict)
    env: dict[str, int] = field(default_factory=dict)  # ppco2 / press -> level
    ppco2_60: float | None = None
    raw: int = 0
    level: int = 0
    source: str | None = None
    learn_mask: int = 0
    pattern: str | None = None
    p: float | None = None

    def z(self, m: str) -> float | None:
        e = self.evals.get(m)
        return e.z if e else None

    def as_row(self) -> dict[str, Any]:
        v = self.v
        row: dict[str, Any] = {
            "crew_id": v.crew_id,
            "ts": datetime.fromtimestamp(v.ts, tz=UTC),
            "hr": v.hr, "spo2": v.spo2, "rr": v.rr, "skin_t": v.skin_t, "hrv": v.hrv,
            "co2_ppm": v.co2_ppm, "press_hpa": v.press_hpa, "amb_t": v.amb_t,
            "ppco2": v.ppco2, "act_mg": v.act_mg, "sqi": v.sqi,
            "worn_frac": v.worn_frac, "valid_s": v.valid_s,
            "ctx": self.ctx, "level": self.level, "learn_mask": self.learn_mask,
        }
        for m in ROW_NORM_METRICS:
            e = self.evals.get(m) or MetricEval()
            row[f"z_{m}"] = e.z
            row[f"lo_{m}"] = e.lo
            row[f"hi_{m}"] = e.hi
        return row

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "MinuteResult":
        """Rebuild enough of a past minute for spark, features and env windows."""
        ts = row["ts"]
        v = MinuteValues(
            crew_id=row["crew_id"],
            ts=int(ts.timestamp()) if isinstance(ts, datetime) else int(ts),
            hr=row.get("hr"), spo2=row.get("spo2"), rr=row.get("rr"),
            skin_t=row.get("skin_t"), hrv=row.get("hrv"), co2_ppm=row.get("co2_ppm"),
            press_hpa=row.get("press_hpa"), amb_t=row.get("amb_t"),
            act_mg=row.get("act_mg"), sqi=row.get("sqi"),
            worn_frac=row.get("worn_frac") or 0.0, valid_s=row.get("valid_s") or 0,
            history=True,
        )
        evals = {}
        for m in ROW_NORM_METRICS:
            lo, hi = row.get(f"lo_{m}"), row.get(f"hi_{m}")
            evals[m] = MetricEval(
                z=row.get(f"z_{m}"), lo=lo, hi=hi,
                med=None if lo is None or hi is None else (lo + hi) / 2,
                learning=lo is None,
            )
        return cls(v=v, ctx=row["ctx"], evals=evals, level=row.get("level") or 0,
                   learn_mask=row.get("learn_mask") or 0)
