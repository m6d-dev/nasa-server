"""Acceptance rule for an LLM answer (BACKEND_TZ §9, step 2).

A wrong number in a health message is worse than a dull one, so the reply is
taken only if it has exactly the three lines and every number in it already
appears in the summary the model was given.
"""

import json
import re
from typing import Any

from src.app.domain.narration.entities.narration import AlertText

# a number not glued to letters, so "SpO2" or "CO2" are not read as 2
_NUM = re.compile(r"(?<![A-Za-z\d.])-?\d+(?:\.\d+)?(?![A-Za-z\d])")
_PREFIXES = ("WHAT:", "WHY:", "ACTION:")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def numbers_in(text: str) -> set[float]:
    return {float(x) for x in _NUM.findall(text)}


def parse_reply(reply: str, summary: dict[str, Any]) -> AlertText | None:
    lines = [ln.strip() for ln in reply.strip().splitlines() if ln.strip()]
    if len(lines) != 3 or any(not ln.startswith(p) for ln, p in zip(lines, _PREFIXES, strict=True)):
        return None
    allowed = numbers_in(json.dumps(summary))
    if not numbers_in("\n".join(lines)) <= allowed:
        return None
    what, why, action = (ln.split(":", 1)[1].strip() for ln in lines)
    if not (what and why and action):
        return None
    steps = tuple(s for s in _SENTENCE.split(action) if s)[:3]
    return AlertText(what=what, why=why, action=steps)
