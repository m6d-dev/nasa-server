"""NASA OSDR RadLab files → daily doses (BACKEND_TZ §12).

The API answers in pandas "split" orient: {"columns": [...], "data": [[...]]}.
A plain list of records is accepted too. Dates stay as in the file: shifting
them to the virtual "today" would be passing off old data as new.
"""

import json
import logging
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from src.app.application.radiation.ports.repositories import RadiationDay

logger = logging.getLogger("vigil.radiation")

# mean rate over a day → dose for that day, in mGy
RATE_TO_MGY_PER_DAY = {"uGy/h": 24 / 1000, "uGy/min": 1440 / 1000, "mGy/day": 1.0}
_TS_KEYS = ("timestamp", "time", "date", "datetime")
_DOSE_KEYS = ("absorbed_dose_rate", "dose_rate", "dose")
_INSTR_KEYS = ("instrument_id", "instrument")


def _records(doc: Any) -> Iterable[dict[str, Any]]:
    if isinstance(doc, dict) and "columns" in doc and "data" in doc:
        cols = doc["columns"]
        return (dict(zip(cols, row, strict=False)) for row in doc["data"])
    if isinstance(doc, dict) and isinstance(doc.get("data"), list):
        return doc["data"]
    if isinstance(doc, list):
        return doc
    return []


def _pick(rec: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((rec[k] for k in keys if k in rec and rec[k] is not None), None)


def load_radlab(directory: str, instrument: str, rate_unit: str) -> list[RadiationDay]:
    samples: dict[tuple[str, date], list[float]] = defaultdict(list)
    for path in sorted(Path(directory).glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            logger.warning("skip %s: %s", path, exc)
            continue
        for rec in _records(doc):
            ts, dose = _pick(rec, _TS_KEYS), _pick(rec, _DOSE_KEYS)
            if ts is None or dose is None:
                continue
            try:
                samples[(str(_pick(rec, _INSTR_KEYS) or "unknown"), date.fromisoformat(str(ts)[:10]))].append(float(dose))
            except ValueError:
                continue
    if not samples:
        return []
    counts = Counter(k[0] for k in samples)
    chosen = instrument if instrument in counts else counts.most_common(1)[0][0]
    factor = RATE_TO_MGY_PER_DAY[rate_unit]
    return [
        RadiationDay(day=d, dose=round(sum(v) / len(v) * factor, 4), unit="mGy", instrument=chosen)
        for (ins, d), v in sorted(samples.items(), key=lambda kv: kv[0][1])
        if ins == chosen
    ]
