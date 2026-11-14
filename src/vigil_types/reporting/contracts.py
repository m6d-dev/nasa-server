from typing import Annotated, Any, Literal

from pydantic import Field

from src.vigil_types.base import DTO, ATCrewId, ATDay, BaseContract, Command, Query
from src.vigil_types.crew.contracts import ATNote

ReportSection = Literal["vitals", "alerts", "sleep", "checkin", "cabin"]
DEFAULT_INCLUDE: dict[str, bool] = {s: True for s in ("vitals", "alerts", "sleep", "checkin", "cabin")}


class ReportUpdateDTO(BaseContract):
    include: Annotated[dict[ReportSection, bool], Field(max_length=5)] | None = None
    note: ATNote | None = None


class ReportUpdateCommand(ReportUpdateDTO, Command):
    crew_id: ATCrewId
    day: ATDay


class ReportQueueCommand(Command):
    crew_id: ATCrewId
    day: ATDay


class ReportGetQuery(Query):
    crew_id: ATCrewId
    day: ATDay


class ReportDTO(DTO):
    day: str
    crew: int
    queued_ts: int | None
    include: dict[str, bool]
    note: str
    body: dict[str, Any]
