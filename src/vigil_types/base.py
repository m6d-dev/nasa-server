from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CREW_ID_MAX = 32767  # crew.id is smallint
DAY_REGEX = r"^\d{4}-\d{2}-\d{2}$"

ATCrewId = Annotated[int, Field(ge=1, le=CREW_ID_MAX)]
ATAlertId = Annotated[int, Field(ge=1)]
ATDay = Annotated[str, StringConstraints(min_length=10, max_length=10, pattern=DAY_REGEX)]
ATTs = Annotated[int, Field(ge=0, le=2**32 - 1)]  # unix seconds, fits the frame's u32

MetricCode = Literal["hr", "spo2", "rr", "skin_t", "ppco2", "press", "amb_t"]
VitalCode = Literal["hr", "spo2", "rr", "skin_t"]
CtxName = Literal["off", "sleep", "rest", "active"]
RangeCode = Literal["1h", "24h", "7d"]


class BaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Command(BaseContract):
    """Changes something. Dispatched with `mediator.send`."""


class Query(BaseContract):
    """Reads only. Dispatched with `mediator.ask`."""


class DTO(BaseModel):
    """Response payload. Not frozen: handlers fill them field by field."""

    model_config = ConfigDict(extra="forbid")
