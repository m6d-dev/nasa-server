"""Minute context, checked top-down (BACKEND_TZ §5.3)."""

from src.app.domain.monitoring.constants.thresholds import (
    ACTIVE_ACT_MG,
    ACTIVE_COOLDOWN_MIN,
    CTX_ACTIVE,
    CTX_OFF,
    CTX_REST,
    CTX_SLEEP,
    OFF_SQI,
    OFF_WORN_FRAC,
    SLEEP_ACT_MG,
    SLEEP_HR_DEFAULT_REST,
    SLEEP_HR_MARGIN,
    SLEEP_STILL_MIN,
)
from src.app.domain.monitoring.entities.minute import MinuteValues


class ContextClassifier:
    __slots__ = ("_still", "_last_ts", "_last_active_ts")

    def __init__(self) -> None:
        self._still = 0
        self._last_ts: int | None = None
        self._last_active_ts: int | None = None

    def classify(self, v: MinuteValues, rest_hr_median: float | None) -> int:
        contiguous = self._last_ts is not None and v.ts - self._last_ts == 60
        self._last_ts = v.ts
        if not contiguous:
            self._still = 0

        if v.worn_frac < OFF_WORN_FRAC or (v.sqi if v.sqi is not None else 0) < OFF_SQI:
            self._still = 0
            return CTX_OFF

        act = v.act_mg
        if (act is not None and act >= ACTIVE_ACT_MG) or v.training:
            self._last_active_ts = v.ts
            self._still = 0
            return CTX_ACTIVE
        if self._last_active_ts is not None and 0 < v.ts - self._last_active_ts <= ACTIVE_COOLDOWN_MIN * 60:
            self._still = 0
            return CTX_ACTIVE

        self._still = self._still + 1 if act is not None and act <= SLEEP_ACT_MG else 0
        if self._still >= SLEEP_STILL_MIN:
            ref = rest_hr_median if rest_hr_median is not None else SLEEP_HR_DEFAULT_REST
            # an unknown pulse does not disprove sleep; stillness already argues for it
            if v.hr is None or v.hr <= ref + SLEEP_HR_MARGIN:
                return CTX_SLEEP
        return CTX_REST

    def reset_to(self, last_ts: int | None) -> None:
        self._still, self._last_ts, self._last_active_ts = 0, last_ts, None
