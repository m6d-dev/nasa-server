"""Levels from the personal norm, hard limits and the cabin (BACKEND_TZ §7.1–7.4)."""

from collections import deque

from src.app.domain.monitoring.constants.thresholds import (
    ALERT,
    CRITICAL,
    CTX_ACTIVE,
    CTX_OFF,
    CTX_REST,
    CTX_SLEEP,
    HARD_MIN_VALID_S,
    HR_ALERT_HIGH,
    HR_CRITICAL_HIGH,
    HR_LOW,
    HYSTERESIS_MIN,
    LEVEL_METRICS,
    PPCO2_ALERT,
    PPCO2_CRITICAL,
    PPCO2_MIN_VALUES,
    PPCO2_WATCH,
    PPCO2_WINDOW_MIN,
    PRESS_BELOW_MEDIAN_CRITICAL,
    PRESS_DROP_ALERT,
    PRESS_DROP_WINDOW_MIN,
    PRESS_MEDIAN_MIN_VALUES,
    PRESS_MEDIAN_WINDOW_MIN,
    RR_ALERT_HIGH,
    RR_CRITICAL_HIGH,
    RR_CRITICAL_LOW,
    SPO2_ALERT_BELOW,
    SPO2_CRITICAL_MAX,
    USUAL,
    WATCH,
    Z_ALERT,
    Z_ALERT_MIN,
    Z_WATCH,
    Z_WATCH_MIN,
)
from src.app.domain.monitoring.entities.minute import MetricEval, MinuteValues
from src.app.domain.monitoring.services.stats import median

# z-levels skip pulse and breathing while exercising (§7.1)
_ACTIVE_EXEMPT = ("hr", "rr")


def hard_level(m: str, x: float | None, ctx: int) -> tuple[int, str | None]:
    """§7.2. Returns (level, direction 'up'|'down')."""
    if x is None or ctx in (CTX_OFF, CTX_ACTIVE):
        return USUAL, None
    if m == "spo2":
        if x <= SPO2_CRITICAL_MAX:
            return CRITICAL, "down"
        if x < SPO2_ALERT_BELOW:
            return ALERT, "down"
    elif m == "hr" and ctx in (CTX_REST, CTX_SLEEP):
        if x >= HR_CRITICAL_HIGH:
            return CRITICAL, "up"
        if x <= HR_LOW:
            return (CRITICAL if ctx == CTX_REST else ALERT), "down"
        if x >= HR_ALERT_HIGH:
            return ALERT, "up"
    elif m == "rr" and ctx in (CTX_REST, CTX_SLEEP):
        if x <= RR_CRITICAL_LOW:
            return CRITICAL, "down"
        if x >= RR_CRITICAL_HIGH:
            return CRITICAL, "up"
        if x >= RR_ALERT_HIGH:
            return ALERT, "up"
    return USUAL, None


def z_counts(m: str, z: float | None) -> bool:
    """SpO2 only counts downwards."""
    return z is not None and (z < 0 if m == "spo2" else True)


class LevelDetector:
    def __init__(self) -> None:
        self._watch: dict[str, int] = {m: 0 for m in LEVEL_METRICS}
        self._alert: dict[str, int] = {m: 0 for m in LEVEL_METRICS}
        self._last_ts: int | None = None
        self._ppco2: deque[tuple[int, float]] = deque()
        self._press: deque[tuple[int, float]] = deque()
        self.level = USUAL
        self._down = 0

    def evaluate(
        self, v: MinuteValues, ctx: int, evals: dict[str, MetricEval]
    ) -> tuple[int, str | None, dict[str, int], float | None, dict[str, str]]:
        """Fills `hard`/`base` on evals. Returns (raw, source, env, ppco2_60, hard_dirs)."""
        if self._last_ts is None or v.ts - self._last_ts != 60:
            for m in LEVEL_METRICS:
                self._watch[m] = self._alert[m] = 0  # a missing minute resets streaks
        self._last_ts = v.ts

        raw, source = USUAL, None
        hard_dirs: dict[str, str] = {}
        hard_ok = v.kind == 2 or v.valid_s >= HARD_MIN_VALID_S

        for m in LEVEL_METRICS:
            e = evals[m]
            x = v.get(m)
            if hard_ok:
                e.hard, d = hard_level(m, x, ctx)
                if d:
                    hard_dirs[m] = d
            e.evaluated = (
                ctx != CTX_OFF and not e.learning and e.z is not None
                and not (ctx == CTX_ACTIVE and m in _ACTIVE_EXEMPT)
            )
            if e.evaluated and z_counts(m, e.z):
                az = abs(e.z)  # type: ignore[arg-type]
                self._watch[m] = self._watch[m] + 1 if az >= Z_WATCH else 0
                self._alert[m] = self._alert[m] + 1 if az >= Z_ALERT else 0
            else:
                self._watch[m] = self._alert[m] = 0
            e.base = ALERT if self._alert[m] >= Z_ALERT_MIN else WATCH if self._watch[m] >= Z_WATCH_MIN else USUAL

        env, ppco2_60 = self._environment(v)
        # on a tie the more objective source names the level
        candidates = [(e.hard, 3, "hard") for e in evals.values()]
        candidates += [(lvl, 2, "env") for lvl in env.values()]
        candidates += [(evals[m].base, 1, "baseline") for m in LEVEL_METRICS]
        best = max(candidates)
        if best[0] > USUAL:
            raw, source = best[0], best[2]
        return raw, source, env, ppco2_60, hard_dirs

    def _environment(self, v: MinuteValues) -> tuple[dict[str, int], float | None]:
        env = {"ppco2": USUAL, "press": USUAL}
        pp = v.ppco2
        if pp is not None:
            self._ppco2.append((v.ts, pp))
        while self._ppco2 and self._ppco2[0][0] <= v.ts - PPCO2_WINDOW_MIN * 60:
            self._ppco2.popleft()
        mean60 = None
        if len(self._ppco2) >= PPCO2_MIN_VALUES:
            mean60 = sum(p[1] for p in self._ppco2) / len(self._ppco2)
            env["ppco2"] = (
                CRITICAL if mean60 > PPCO2_CRITICAL else ALERT if mean60 > PPCO2_ALERT
                else WATCH if mean60 > PPCO2_WATCH else USUAL
            )

        p = v.press_hpa
        while self._press and self._press[0][0] <= v.ts - PRESS_MEDIAN_WINDOW_MIN * 60:
            self._press.popleft()
        if p is not None:
            recent = [x for t, x in self._press if t > v.ts - PRESS_DROP_WINDOW_MIN * 60]
            if recent and (max(recent) - p) / max(recent) > PRESS_DROP_ALERT:
                env["press"] = ALERT
            if len(self._press) >= PRESS_MEDIAN_MIN_VALUES:
                med = median([x for _, x in self._press])
                if med and (med - p) / med > PRESS_BELOW_MEDIAN_CRITICAL:
                    env["press"] = CRITICAL
            self._press.append((v.ts, p))
        return env, mean60

    def press_median(self) -> float | None:
        return median([x for _, x in self._press]) if self._press else None

    def feed_env(self, v: MinuteValues) -> None:
        """Restore path: refill cabin windows without judging."""
        if v.ppco2 is not None:
            self._ppco2.append((v.ts, v.ppco2))
        if v.press_hpa is not None:
            self._press.append((v.ts, v.press_hpa))
        self._last_ts = None

    def apply_hysteresis(self, raw: int) -> int:
        """Up at once; down one step after 10 received minutes below (§7.4)."""
        if raw > self.level:
            self.level, self._down = raw, 0
        elif raw < self.level:
            self._down += 1
            if self._down >= HYSTERESIS_MIN:
                self.level -= 1
                self._down = 0
        else:
            self._down = 0
        return self.level
