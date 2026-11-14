"""The 40 pattern features (PLAN.md §10). One code path for ML offline and the server.

Features are in z-units of the personal norm, so the model does not care whose
data it is. Missing values are NaN; XGBoost handles them.
"""

import math
from collections.abc import Sequence

import numpy as np

from src.app.domain.monitoring.constants.thresholds import CTX_ACTIVE, CTX_REST, CTX_SLEEP
from src.app.domain.monitoring.entities.minute import MinuteResult
from src.app.domain.monitoring.services.stats import median, slope_per_min

NAN = float("nan")
Z_METRICS = ("hr", "spo2", "rr", "skin_t")

FEATURE_NAMES: tuple[str, ...] = (
    *(f"{m}_{s}" for m in Z_METRICS for s in ("z_last", "z_mean", "z_min", "z_max", "z_slope", "valid_frac")),
    "hrv_z_last",
    "act_mean", "act_max", "act_std",
    "ctx_rest", "ctx_active", "ctx_sleep",
    "ppco2_mean", "ppco2_slope",
    "press_dev24", "press_slope",
    "sqi_mean", "sqi_min", "worn_frac_mean",
    "tod_sin", "tod_cos",
)
assert len(FEATURE_NAMES) == 40


def _nan(x: float | None) -> float:
    return NAN if x is None else float(x)


def build_features(window: Sequence[MinuteResult], press_median_24h: float | None) -> dict[str, float]:
    last = window[-1]
    n = len(window)
    out: dict[str, float] = {}
    for m in Z_METRICS:
        pts = [(r.v.ts, r.z(m)) for r in window if r.z(m) is not None]
        zs = [p[1] for p in pts]
        out[f"{m}_z_last"] = _nan(last.z(m))
        out[f"{m}_z_mean"] = float(np.mean(zs)) if zs else NAN
        out[f"{m}_z_min"] = min(zs) if zs else NAN
        out[f"{m}_z_max"] = max(zs) if zs else NAN
        out[f"{m}_z_slope"] = _nan(slope_per_min(pts))  # type: ignore[arg-type]
        out[f"{m}_valid_frac"] = sum(1 for r in window if r.v.get(m) is not None) / n
    out["hrv_z_last"] = _nan(last.z("hrv"))

    acts = [r.v.act_mg for r in window if r.v.act_mg is not None]
    out["act_mean"] = float(np.mean(acts)) if acts else NAN
    out["act_max"] = max(acts) if acts else NAN
    out["act_std"] = float(np.std(acts)) if acts else NAN

    out["ctx_rest"] = float(last.ctx == CTX_REST)
    out["ctx_active"] = float(last.ctx == CTX_ACTIVE)
    out["ctx_sleep"] = float(last.ctx == CTX_SLEEP)

    pp = [(r.v.ts, r.v.ppco2) for r in window if r.v.ppco2 is not None]
    out["ppco2_mean"] = float(np.mean([p[1] for p in pp])) if pp else NAN
    out["ppco2_slope"] = _nan(slope_per_min(pp))  # type: ignore[arg-type]

    pr = [(r.v.ts, r.v.press_hpa) for r in window if r.v.press_hpa is not None]
    ref = press_median_24h if press_median_24h is not None else median([p[1] for p in pr])  # type: ignore[misc]
    out["press_dev24"] = (pr[-1][1] - ref) / ref if pr and ref else NAN  # type: ignore[operator]
    out["press_slope"] = _nan(slope_per_min(pr))  # type: ignore[arg-type]

    sq = [r.v.sqi for r in window if r.v.sqi is not None]
    out["sqi_mean"] = float(np.mean(sq)) if sq else NAN
    out["sqi_min"] = min(sq) if sq else NAN
    out["worn_frac_mean"] = float(np.mean([r.v.worn_frac for r in window]))

    angle = 2 * math.pi * (last.v.ts % 86400) / 86400
    out["tod_sin"], out["tod_cos"] = math.sin(angle), math.cos(angle)
    return out
