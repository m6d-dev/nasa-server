"""Daily report body (BACKEND_TZ §11.8). All sections are always built; what is
shared is decided by `include` on the frontend, `coverage` is never hidden."""

from datetime import UTC, date, datetime
from statistics import median
from typing import Any

from src.app.application.reporting.ports.repositories import ReportRecord
from src.app.application.reporting.ports.sources import (
    CheckinSourceProto,
    MonitoringFactsProto,
)
from src.app.domain.monitoring.constants.thresholds import (
    CTX_OFF,
    CTX_REST,
    LEVEL_NAMES,
    PPCO2_WATCH,
    rnd,
)
from src.vigil_types.reporting.contracts import DEFAULT_INCLUDE

DAY = 86400
VITALS = ("hr", "spo2", "rr", "skin_t")


def day_bounds(d: date) -> tuple[int, int]:
    start = int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())
    return start, start + DAY


def build_body(
    rows: list[dict[str, Any]],
    incidents: list,
    night: Any,
    checkin: Any | None,
    baseline_state: str,
    minutes_in_day: int,
    now_ts: int | None,
) -> dict[str, Any]:
    vitals: dict[str, Any] = {}
    for m in VITALS:
        vals = [r[m] for r in rows if r[m] is not None and r["ctx"] != CTX_OFF]
        rest = [r[m] for r in rows if r[m] is not None and r["ctx"] == CTX_REST]
        last_band = next(((r[f"lo_{m}"], r[f"hi_{m}"]) for r in reversed(rows)
                          if r["ctx"] == CTX_REST and r[f"lo_{m}"] is not None), None)
        vitals[m] = {
            "rest_median": rnd(m, median(rest)) if rest else None,
            "min": rnd(m, min(vals)) if vals else None,
            "max": rnd(m, max(vals)) if vals else None,
            "usual": [rnd(m, last_band[0]), rnd(m, last_band[1])] if last_band else None,
        }

    levels = {name: 0 for name in LEVEL_NAMES.values()}
    for r in rows:
        if r["ctx"] != CTX_OFF:
            levels[LEVEL_NAMES[r["level"]]] += 1

    pp = [r["ppco2"] for r in rows if r["ppco2"] is not None]
    data_min = sum(1 for r in rows if r["ctx"] != CTX_OFF)

    return {
        "vitals": vitals,
        "levels_min": levels,
        "alerts": [
            {"ts_start": a.ts_start,
             "minutes": max(0, ((a.ts_end if a.ts_end is not None else (now_ts or a.ts_start)) - a.ts_start) // 60),
             "peak_level": a.peak_level, "pattern": a.pattern, "acked": a.acked}
            for a in incidents
        ],
        "sleep": {"minutes": night.minutes, "onset_ts": night.onset_ts},
        "checkin": None if checkin is None else {
            "filed_ts": checkin.filed_ts, "sleep_q": checkin.sleep_q, "mood": checkin.mood,
            "energy": checkin.energy, "symptoms": list(checkin.symptoms), "note": checkin.note,
        },
        "cabin": {
            "ppco2_mean": rnd("ppco2", sum(pp) / len(pp)) if pp else None,
            "ppco2_max": rnd("ppco2", max(pp)) if pp else None,
            "minutes_above_limit": sum(1 for x in pp if x > PPCO2_WATCH),
        },
        "coverage": {"data_min": data_min, "nodata_min": max(0, minutes_in_day - data_min)},
        "baseline": {"state": baseline_state},
    }


class ReportBuilder:
    def __init__(self, facts: MonitoringFactsProto, checkins: CheckinSourceProto) -> None:
        self._facts, self._checkins = facts, checkins

    async def build(self, crew_id: int, d: date, saved: ReportRecord | None) -> ReportRecord:
        start, end = day_bounds(d)
        now = self._facts.now_ts(crew_id)
        # for the current day only the elapsed part counts as "no data"
        span_end = min(end, (now - now % 60 + 60)) if now is not None and now < end else end
        minutes = max(0, (span_end - start) // 60)
        body = build_body(
            rows=await self._facts.minute_rows(crew_id, start, end),
            incidents=await self._facts.incidents(crew_id, start, end),
            night=await self._facts.night(crew_id, d),
            checkin=await self._checkins.get(crew_id, d),
            baseline_state=self._facts.baseline_state(crew_id),
            minutes_in_day=minutes,
            now_ts=now,
        )
        return ReportRecord(
            crew_id=crew_id, day=d, body=body,
            include=saved.include if saved else dict(DEFAULT_INCLUDE),
            note=saved.note if saved else "",
            queued_ts=saved.queued_ts if saved else None,
        )
