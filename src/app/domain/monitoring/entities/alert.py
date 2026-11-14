from dataclasses import dataclass, field
from typing import Any

KEY_INCIDENT = "incident"
KEY_BASELINE_LEARNED = "baseline_learned"
CHECKIN_KEY_PREFIX = "checkin:"


@dataclass(slots=True)
class IncidentMetric:
    m: str
    value: float | None
    lo: float | None
    hi: float | None
    z: float | None
    slope_per_min: float | None
    since_ts: int
    trend: str
    direction: str | None
    hard: int = 0


@dataclass(slots=True)
class AlertEntity:
    """A row of `alert`: the one open incident of a person, or a system notice
    (level 0, source 'system'; BACKEND_TZ §7.5–7.6)."""

    crew_id: int
    key: str
    source: str
    ts_start: int
    ts_update: int
    level: int = 0
    peak_level: int = 0
    id: int | None = None
    ts_end: int | None = None
    pattern: str | None = None
    p: float | None = None
    ctx: int | None = None
    primary: str | None = None
    metrics: list[IncidentMetric] = field(default_factory=list)
    text: dict[str, Any] | None = None
    text_src: str | None = None
    ack_ts: int | None = None
    # bumps on every text replacement, so a late LLM answer for an old state is dropped
    text_rev: int = 0

    @property
    def is_open(self) -> bool:
        return self.ts_end is None

    @property
    def is_incident(self) -> bool:
        return self.key == KEY_INCIDENT

    def metrics_json(self) -> list[dict[str, Any]]:
        return [
            {"m": x.m, "value": x.value, "lo": x.lo, "hi": x.hi, "z": x.z,
             "slope_per_min": x.slope_per_min, "since_ts": x.since_ts, "trend": x.trend,
             "direction": x.direction, "hard": x.hard}
            for x in self.metrics
        ]

    @staticmethod
    def metrics_from_json(items: list[dict[str, Any]]) -> list[IncidentMetric]:
        return [
            IncidentMetric(
                m=d["m"], value=d.get("value"), lo=d.get("lo"), hi=d.get("hi"), z=d.get("z"),
                slope_per_min=d.get("slope_per_min"), since_ts=d.get("since_ts") or 0,
                trend=d.get("trend") or "stable", direction=d.get("direction"), hard=d.get("hard") or 0,
            )
            for d in items
        ]
