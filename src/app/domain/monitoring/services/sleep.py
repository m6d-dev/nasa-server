"""Nights from the minute context (BACKEND_TZ §11.7)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from src.app.domain.monitoring.constants.thresholds import CTX_SLEEP

NIGHT_FROM_H = 18  # previous day
NIGHT_TO_H = 12
MAX_GAP_MIN = 10


@dataclass(slots=True, frozen=True)
class Night:
    day: date  # the morning the night ends on
    onset_ts: int | None
    wake_ts: int | None
    minutes: int | None


def night_window(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(hours=24 - NIGHT_FROM_H)
    end = datetime(day.year, day.month, day.day, NIGHT_TO_H, tzinfo=UTC)
    return int(start.timestamp()), int(end.timestamp())


def find_night(day: date, ctx_rows: Iterable[tuple[int, int]]) -> Night:
    """Longest run of `sleep` in the window; gaps up to 10 minutes are glued."""
    lo, hi = night_window(day)
    sleep_ts = sorted(ts for ts, ctx in ctx_rows if ctx == CTX_SLEEP and lo <= ts < hi)
    best: tuple[int, int] | None = None
    run_start = prev = None
    for ts in sleep_ts:
        if prev is None or ts - prev > (MAX_GAP_MIN + 1) * 60:
            run_start = ts
        prev = ts
        if best is None or (ts - run_start) > (best[1] - best[0]):  # type: ignore[operator]
            best = (run_start, ts)  # type: ignore[assignment]
    if best is None:
        return Night(day, None, None, None)
    onset, last = best
    return Night(day, onset, last + 60, (last + 60 - onset) // 60)


def nights(days: list[date], ctx_rows: list[tuple[int, int]]) -> list[Night]:
    return [find_night(d, ctx_rows) for d in days]
