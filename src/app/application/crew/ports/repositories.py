from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CrewInfo:
    id: int
    name: str
    role: str
    dev_id: int
    share: dict[str, bool] = field(default_factory=dict)

    def shares(self, what: str) -> bool:
        return bool(self.share.get(what, True))


@dataclass(frozen=True, slots=True)
class CheckinRecord:
    crew_id: int
    day: date
    filed_ts: int
    sleep_q: int | None = None
    mood: int | None = None
    energy: int | None = None
    symptoms: tuple[str, ...] = ()
    note: str | None = None


class CrewRepositoryProto(Protocol):
    async def list_all(self) -> list[CrewInfo]: ...


class CheckinRepositoryProto(Protocol):
    async def get(self, crew_id: int, day: date) -> CheckinRecord | None: ...

    async def upsert(self, rec: CheckinRecord) -> None: ...

    async def list_since(self, day: date) -> list[CheckinRecord]: ...
