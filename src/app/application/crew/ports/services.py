from dataclasses import dataclass
from datetime import date
from typing import Protocol


class CrewClockProto(Protocol):
    """Virtual time of a person (BACKEND_TZ §4). Bound to the monitoring engine."""

    def now_ts(self, crew_id: int) -> int | None: ...

    def today(self, crew_id: int) -> date | None: ...

    def has_crew(self, crew_id: int) -> bool: ...


@dataclass(frozen=True, slots=True)
class CheckinFiled:
    """Event: monitoring closes the To-do notice and feeds symptoms to the text."""

    crew_id: int
    day: date
    symptoms: tuple[str, ...]
