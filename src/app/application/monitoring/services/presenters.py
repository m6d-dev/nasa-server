"""State → response DTOs. Shared by query handlers and /live messages."""

from src.app.application.monitoring.services.device_registry import DeviceState
from src.app.domain.monitoring.aggregates.crew_monitor import CrewMonitorAggregate
from src.app.domain.monitoring.constants.thresholds import (
    CTX_ACTIVE,
    CTX_NAMES,
    HR_ALERT_HIGH,
    HR_CRITICAL_HIGH,
    HR_LOW,
    LEVEL_NAMES,
    PPCO2_ALERT,
    PPCO2_CRITICAL,
    PPCO2_WATCH,
    RR_ALERT_HIGH,
    RR_CRITICAL_HIGH,
    RR_CRITICAL_LOW,
    SPO2_CRITICAL_MAX,
    UNITS,
    rnd,
)
from src.app.domain.monitoring.entities.alert import AlertEntity
from src.app.domain.monitoring.entities.minute import MinuteResult
from src.vigil_types.monitoring.dto import (
    AlertMetricDTO,
    AlertTextDTO,
    BaselineDTO,
    MetricLimitDTO,
    NoticeDTO,
    VitalCardDTO,
)

VITALS = ("hr", "spo2", "rr", "skin_t")
CABIN = ("ppco2", "press", "amb_t")
STALE_AFTER_S = 120  # a last minute older than this is not "now"

# the one number a card shows as its limit (§11.2 example: spo2 → 91)
CARD_LIMIT = {"spo2": SPO2_CRITICAL_MAX, "hr": HR_CRITICAL_HIGH, "rr": RR_CRITICAL_HIGH, "ppco2": PPCO2_WATCH}

CHART_LIMITS: dict[str, list[tuple[float, str]]] = {
    "spo2": [(SPO2_CRITICAL_MAX, "critical_below"), (93.0, "alert_below")],
    "hr": [(HR_ALERT_HIGH, "alert_above"), (HR_CRITICAL_HIGH, "critical_above"), (HR_LOW, "critical_below")],
    "rr": [(RR_ALERT_HIGH, "alert_above"), (RR_CRITICAL_HIGH, "critical_above"), (RR_CRITICAL_LOW, "critical_below")],
    "ppco2": [(PPCO2_WATCH, "watch_above"), (PPCO2_ALERT, "alert_above"), (PPCO2_CRITICAL, "critical_above")],
}


def chart_limits(m: str) -> list[MetricLimitDTO]:
    return [MetricLimitDTO(value=v, kind=k) for v, k in CHART_LIMITS.get(m, [])]  # type: ignore[arg-type]


def signal_of(sqi: float | None) -> str | None:
    if sqi is None:
        return None
    return "good" if sqi >= 70 else "fair" if sqi >= 40 else "poor"


def baseline_dto(agg: CrewMonitorAggregate) -> BaselineDTO:
    ls = agg.learn
    return BaselineDTO(state=ls.state, day=min(ls.days, 7), of=7, ready_pct=ls.ready_pct)  # type: ignore[arg-type]


def current_minute(agg: CrewMonitorAggregate, now_ts: int | None, link: str) -> MinuteResult | None:
    last = agg.last
    if last is None or now_ts is None or link != "connected":
        return None
    return last if now_ts - last.v.ts <= STALE_AFTER_S else None


def band(r: MinuteResult | None, m: str) -> list | None:
    e = r.evals.get(m) if r else None
    if e is None or e.learning or e.lo is None or e.hi is None:
        return None
    return [rnd(m, e.lo), rnd(m, e.hi)]


def spark(agg: CrewMonitorAggregate, m: str, end_ts: int | None) -> list:
    if end_ts is None:
        return [None] * 60
    by_ts = {r.v.ts: r.v.get(m) for r in agg.window}
    return [rnd(m, by_ts.get(end_ts - 60 * i)) for i in range(59, -1, -1)]


def card_state(m: str, agg: CrewMonitorAggregate, dev: DeviceState | None, cur: MinuteResult | None) -> tuple[str, float | None, int | None]:
    """§11.2 precedence: not_measured → no_data → hard → exercising → learning → norm → usual."""
    if dev is None or m not in dev.channels:
        return "not_measured", None, None
    value = cur.v.get(m) if cur else None
    if value is None:
        since = next((r.v.ts + 60 for r in reversed(agg.window) if r.v.get(m) is not None), None)
        return "no_data", None, since
    if m in CABIN:
        lvl = cur.env.get(m, 0) if m != "amb_t" else 0  # type: ignore[union-attr]
        return LEVEL_NAMES[lvl], value, None
    e = cur.evals[m]  # type: ignore[union-attr]
    if e.hard:
        return LEVEL_NAMES[e.hard], value, None
    if cur.ctx == CTX_ACTIVE and m in ("hr", "rr"):  # type: ignore[union-attr]
        return "exercising", value, None
    if e.learning:
        return "learning", value, None
    if e.base:
        return LEVEL_NAMES[e.base], value, None
    return "usual", value, None


def vital_card(m: str, agg: CrewMonitorAggregate, dev: DeviceState | None, cur: MinuteResult | None) -> VitalCardDTO:
    state, value, since = card_state(m, agg, dev, cur)
    end = agg.last.v.ts if agg.last else None
    learning = m in VITALS and (cur.evals[m].learning if cur else (agg.last.evals[m].learning if agg.last else True))
    b = None if m in CABIN else band(cur or agg.last, m)
    shown = rnd(m, cur.ppco2_60 if m == "ppco2" and cur and cur.ppco2_60 is not None else value)
    return VitalCardDTO(
        m=m, value=shown, unit=UNITS[m], state=state, learning=learning,  # type: ignore[arg-type]
        usual=b, limit=CARD_LIMIT.get(m), spark=spark(agg, m, end), band=b, since_ts=since,
    )


def notice_dto(a: AlertEntity, now_ts: int | None) -> NoticeDTO:
    end = a.ts_end if a.ts_end is not None else (now_ts or a.ts_update)
    metrics = [
        AlertMetricDTO(
            m=x.m, value=rnd(x.m, x.value),
            usual=[rnd(x.m, x.lo), rnd(x.m, x.hi)] if x.lo is not None and x.hi is not None else None,
            z=None if x.z is None else round(x.z, 1), trend=x.trend,  # type: ignore[arg-type]
            since_min=max(0, (end - x.since_ts) // 60),
            slope_per_min=None if x.slope_per_min is None else round(x.slope_per_min, 3),
        )
        for x in a.metrics
    ]
    return NoticeDTO(
        id=a.id or 0, crew=a.crew_id, key=a.key, source=a.source,
        level=a.level, peak_level=a.peak_level, ts_start=a.ts_start, ts_end=a.ts_end,
        since_min=max(0, (end - a.ts_start) // 60),
        pattern=a.pattern, p=None if a.p is None else round(a.p, 2),
        ctx=CTX_NAMES.get(a.ctx) if a.ctx is not None else None,  # type: ignore[arg-type]
        primary=a.primary, metrics=metrics,
        text=AlertTextDTO(**a.text) if a.text else None,
        text_src=a.text_src, ack_ts=a.ack_ts,  # type: ignore[arg-type]
    )
