"""Personal norm (BACKEND_TZ §6). No table of its own: rebuilt from agg_1m."""

from collections import deque
from dataclasses import dataclass
from typing import NamedTuple

from src.app.domain.monitoring.constants.thresholds import (
    BAND_SIGMAS,
    BUFFER_DAYS,
    BUFFER_MAX,
    CELL_READY_DAYS,
    CELL_READY_N,
    CTX_ACTIVE,
    CTX_NAMES,
    CTX_REST,
    LEARNED_DAYS,
    LEARNED_READY_PCT,
    SIGMA_FLOOR,
    TYPICAL_NORM,
)
from src.app.domain.monitoring.services.stats import robust_stats

DAY = 86400


def tod_of(ts: int, ctx: int) -> int:
    return 0 if ctx == CTX_ACTIVE else (ts // 3600 % 24) // 4


class Norm(NamedTuple):
    med: float
    sig: float
    learning: bool  # True -> typical norm, levels by z are off

    @property
    def band(self) -> tuple[float, float]:
        return self.med - BAND_SIGMAS * self.sig, self.med + BAND_SIGMAS * self.sig


@dataclass(slots=True)
class _Stats:
    med: float
    sig: float
    n: int
    ndays: int

    @property
    def ready(self) -> bool:
        return self.n >= CELL_READY_N and self.ndays >= CELL_READY_DAYS


class NormCell:
    __slots__ = ("buf", "stats", "dirty")

    def __init__(self) -> None:
        self.buf: deque[tuple[int, float]] = deque(maxlen=BUFFER_MAX)  # (ts, value)
        self.stats: _Stats | None = None
        self.dirty = False

    def trim(self, oldest_ts: int) -> None:
        while self.buf and self.buf[0][0] < oldest_ts:
            self.buf.popleft()
            self.dirty = True


def _stats(points: list[tuple[int, float]], metric: str) -> _Stats | None:
    if not points:
        return None
    med, sig = robust_stats([p[1] for p in points], SIGMA_FLOOR[metric])
    return _Stats(med, sig, len(points), len({p[0] // DAY for p in points}))


class LearnState(NamedTuple):
    state: str  # "learning" | "learned"
    days: int
    ready_pct: int


class PersonalBaseline:
    def __init__(self) -> None:
        self._cells: dict[tuple[str, int, int], NormCell] = {}
        self._merged: dict[tuple[str, int], _Stats | None] = {}
        self._recalc_hour: int | None = None
        self._days: set[int] = set()

    # --- feeding ---

    def admit(self, metric: str, ctx: int, ts: int, value: float) -> None:
        key = (metric, ctx, tod_of(ts, ctx))
        cell = self._cells.get(key)
        if cell is None:
            cell = self._cells[key] = NormCell()
        cell.buf.append((ts, value))
        cell.dirty = True

    def note_day(self, ts: int) -> None:
        self._days.add(ts // DAY)

    # --- statistics ---

    def maybe_recalc(self, ts: int) -> None:
        """Statistics move once per virtual hour (§6.2)."""
        hour = ts // 3600
        if hour != self._recalc_hour:
            self.recalc(ts)

    def recalc(self, now_ts: int) -> None:
        self._recalc_hour = now_ts // 3600
        oldest = now_ts - BUFFER_DAYS * DAY
        self._days = {d for d in self._days if d >= oldest // DAY}
        dirty_groups: set[tuple[str, int]] = set()
        for (m, ctx, _tod), cell in self._cells.items():
            cell.trim(oldest)
            if cell.dirty:
                cell.stats = _stats(list(cell.buf), m)
                cell.dirty = False
                dirty_groups.add((m, ctx))
        for m, ctx in dirty_groups:
            pts: list[tuple[int, float]] = []
            for (cm, cc, _t), cell in self._cells.items():
                if cm == m and cc == ctx:
                    pts.extend(cell.buf)
            self._merged[(m, ctx)] = _stats(pts, m)

    def norm(self, metric: str, ctx: int, ts: int) -> Norm | None:
        """§6.3: own cell → same context any time of day → typical norm (learning)."""
        cell = self._cells.get((metric, ctx, tod_of(ts, ctx)))
        if cell is not None and cell.stats is not None and cell.stats.ready:
            return Norm(cell.stats.med, cell.stats.sig, False)
        merged = self._merged.get((metric, ctx))
        if merged is not None and merged.ready:
            return Norm(merged.med, merged.sig, False)
        typical = TYPICAL_NORM.get((metric, CTX_NAMES[ctx])) or TYPICAL_NORM.get((metric, None))
        if typical is None:
            return None
        return Norm(typical[0], typical[1] * 2, True)

    def rest_hr_median(self) -> float | None:
        s = self._merged.get(("hr", CTX_REST))
        return s.med if s is not None and s.ready else None

    def learn_state(self) -> LearnState:
        nonempty = [c for c in self._cells.values() if c.buf]
        ready = sum(1 for c in nonempty if c.stats is not None and c.stats.ready)
        pct = int(100 * ready / len(nonempty)) if nonempty else 0
        days = len(self._days)
        learned = days >= LEARNED_DAYS and pct >= LEARNED_READY_PCT
        return LearnState("learned" if learned else "learning", days, pct)

    def clear(self) -> None:
        self.__init__()
