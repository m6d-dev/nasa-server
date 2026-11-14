from typing import Annotated

from pydantic import Field, StringConstraints

from src.vigil_types.base import DTO, ATCrewId, BaseContract, Command, Query

SYMPTOM_MAX_LENGTH = 40
SYMPTOM_REGEX = r"^[a-z][a-z0-9_]*$"  # keys like "headache", "nausea"
NOTE_MAX_LENGTH = 500
SYMPTOMS_MAX = 12

ATScore = Annotated[int, Field(ge=1, le=5)]
ATSymptom = Annotated[
    str, StringConstraints(min_length=1, max_length=SYMPTOM_MAX_LENGTH, pattern=SYMPTOM_REGEX)
]
# one paragraph of free text; no control characters except newline
ATNote = Annotated[str, StringConstraints(max_length=NOTE_MAX_LENGTH, pattern=r"^[^\x00-\x09\x0b-\x1f]*$")]


class CheckinDTO(BaseContract):
    sleep_q: ATScore | None = None
    mood: ATScore | None = None
    energy: ATScore | None = None
    symptoms: Annotated[list[ATSymptom], Field(max_length=SYMPTOMS_MAX)] = []
    note: ATNote | None = None


class CheckinFileCommand(CheckinDTO, Command):
    crew_id: ATCrewId  # from the path


class CheckinGetQuery(Query):
    crew_id: ATCrewId


class CheckinViewDTO(DTO):
    day: str | None
    filed_ts: int | None
    sleep_q: int | None = None
    mood: int | None = None
    energy: int | None = None
    symptoms: list[str] = []
    note: str | None = None
