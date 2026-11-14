"""Synchronous template text (BACKEND_TZ §9, step 1). Always available."""

from src.app.domain.monitoring.constants.thresholds import UNITS
from src.app.domain.narration.entities.narration import (
    ActionLibrary,
    AlertText,
    NarrationInput,
    NarrationMetric,
)

LABELS = {
    "hr": "Heart rate", "spo2": "Blood oxygen", "rr": "Breathing rate",
    "skin_t": "Skin temperature", "hrv": "Heart rate variability",
    "ppco2": "Cabin CO2", "press": "Cabin pressure", "amb_t": "Cabin temperature",
}
PATTERN_PHRASE = {
    "hypoxia": "low blood oxygen",
    "tachycardia_rest": "a fast heart rate at rest",
    "bradycardia": "a slow heart rate",
    "fever_like": "a fever-like rise in temperature",
    "hypercapnia": "high cabin CO2",
    "depressurization": "a drop in cabin pressure",
    "sensor_artifact": "a sensor fault rather than a body change",
}
CTX_PHRASE = {"rest": "at rest", "sleep": "during sleep", "active": "during exercise"}
TREND_WORD = {"rising": "rising", "falling": "falling", "stable": "steady"}


def _fmt(v: float | int | None) -> str:
    return "—" if v is None else str(v)


def _unit(m: str) -> str:
    u = UNITS.get(m, "")
    return u if u in ("%", "°C") else f" {u}"


def _reading(x: NarrationMetric) -> str:
    s = f"{_fmt(x.value)}{_unit(x.m)}"
    if x.usual:
        s += f", usual {_fmt(x.usual[0])}–{_fmt(x.usual[1])}"
    return s


def _what(x: NarrationMetric, since_min: int) -> str:
    label = LABELS.get(x.m, x.m)
    if x.m == "ppco2":
        return f"{label} averaged {_fmt(x.value)} mmHg over the last hour, above the {_fmt(x.limit)} mmHg limit."
    if x.m == "press":
        return f"{label} is dropping ({_fmt(x.value)} hPa)."
    if x.limit is not None:  # a hard limit fired: the limit matters more than the norm
        where = "below" if x.direction == "down" else "above"
        s = f"{label} is {_fmt(x.value)}{_unit(x.m)}, {where} the safety limit of {_fmt(x.limit)}"
        return s + (f" (usual {_fmt(x.usual[0])}–{_fmt(x.usual[1])})." if x.usual else ".")
    where = "below" if x.direction == "down" else "above"
    return f"{label} has been {where} your usual range for {since_min} minutes ({_reading(x)})."


def compose(inp: NarrationInput, actions: ActionLibrary) -> AlertText:
    primary = next((x for x in inp.metrics if x.m == inp.primary), inp.metrics[0] if inp.metrics else None)
    what = _what(primary, inp.since_min) if primary else "Readings are outside your usual range."

    phrase = PATTERN_PHRASE.get(inp.pattern or "", "an unusual reading")
    why = f"The pattern looks like {phrase}"
    if inp.ctx in CTX_PHRASE:
        why += f", {CTX_PHRASE[inp.ctx]}"
    why += "."
    others = [x for x in inp.metrics if x is not primary and x.m not in ("ppco2", "press")]
    if others:
        why += " " + " ".join(
            f"{LABELS.get(x.m, x.m)} is {TREND_WORD.get(x.trend, 'steady')} ({_reading(x)})." for x in others
        )
    if "ppco2" in inp.env and (primary is None or primary.m != "ppco2"):
        why += f" Cabin CO2 is {_fmt(inp.env['ppco2'])} mmHg."
    if "pressure" in inp.env and (primary is None or primary.m != "press"):
        why += f" Cabin pressure is {inp.env['pressure']}."

    lines = tuple(actions.text(k) for k in inp.actions) or ("Add this to the report for the ground team.",)
    return AlertText(what=what, why=why, action=lines)
