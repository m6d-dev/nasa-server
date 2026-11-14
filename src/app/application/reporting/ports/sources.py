from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class IncidentFact:
    ts_start: int
    ts_end: int | None
    peak_level: int
    pattern: str | None
    acked: bool


@dataclass(frozen=True, slots=True)
class NightFact:
    minutes: int | None
    onset_ts: int | None


class MonitoringFactsProto(Protocol):
    """What reporting needs from monitoring. Implemented by monitoring, bound in DI."""

    def has_crew(self, crew_id: int) -> bool: ...

    def now_ts(self, crew_id: int) -> int | None: ...

    def baseline_state(self, crew_id: int) -> str: ...

    async def flush(self) -> None: ...

    async def minute_rows(self, crew_id: int, start_ts: int, end_ts: int) -> list[dict[str, Any]]: ...

    async def incidents(self, crew_id: int, start_ts: int, end_ts: int) -> list[IncidentFact]: ...

    async def night(self, crew_id: int, day: date) -> NightFact: ...


class CheckinSourceProto(Protocol):
    async def get(self, crew_id: int, day: date) -> Any | None: ...
