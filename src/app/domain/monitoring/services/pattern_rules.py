"""Pattern without a model, from the primary metric (BACKEND_TZ §8.3)."""

from src.app.domain.monitoring.constants.thresholds import CTX_REST, CTX_SLEEP


def pattern_by_rule(primary: str | None, direction: str | None, ctx: int | None) -> str | None:
    if primary == "spo2" and direction == "down":
        return "hypoxia"
    if primary == "hr" and direction == "up" and ctx in (CTX_REST, CTX_SLEEP):
        return "tachycardia_rest"
    if primary == "hr" and direction == "down":
        return "bradycardia"
    if primary == "skin_t" and direction == "up":
        return "fever_like"
    if primary == "ppco2":
        return "hypercapnia"
    if primary == "press":
        return "depressurization"
    return None
