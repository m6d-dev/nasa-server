from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(slots=True)
class ReportRecord:
    crew_id: int
    day: date
    body: dict[str, Any]
    include: dict[str, bool]
    note: str | None = None
    queued_ts: int | None = None


class ReportRepositoryProto(Protocol):
    async def get(self, crew_id: int, day: date) -> ReportRecord | None: ...

    async def save(self, rec: ReportRecord) -> None: ...
