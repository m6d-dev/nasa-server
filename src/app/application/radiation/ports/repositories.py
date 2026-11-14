from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RadiationDay:
    day: date
    dose: float
    unit: str
    instrument: str


class RadiationRepositoryProto(Protocol):
    async def replace_all(self, days: list[RadiationDay]) -> None: ...

    async def list_all(self) -> list[RadiationDay]: ...
