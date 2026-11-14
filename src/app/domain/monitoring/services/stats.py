from collections.abc import Sequence

import numpy as np


def median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def robust_stats(values: Sequence[float], sigma_floor: float) -> tuple[float, float]:
    """(med, sig) with sig = max(1.4826·MAD, floor) — BACKEND_TZ §6.2."""
    a = np.asarray(values, dtype=np.float64)
    med = float(np.median(a))
    mad = float(np.median(np.abs(a - med)))
    return med, max(1.4826 * mad, sigma_floor)


def slope_per_min(points: Sequence[tuple[int, float]]) -> float | None:
    """Least-squares slope in units per minute; needs >= 3 points."""
    if len(points) < 3:
        return None
    t = np.asarray([p[0] for p in points], dtype=np.float64) / 60.0
    y = np.asarray([p[1] for p in points], dtype=np.float64)
    t -= t.mean()
    denom = float((t * t).sum())
    if denom == 0:
        return None
    return float((t * (y - y.mean())).sum() / denom)
