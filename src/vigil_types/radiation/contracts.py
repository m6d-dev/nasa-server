from src.vigil_types.base import DTO, Query


class RadiationQuery(Query): ...


class RadiationDayDTO(DTO):
    day: str
    dose: float


class RadiationDTO(DTO):
    unit: str
    instrument: str | None
    source: str = "NASA OSDR RadLab"
    last_24h: float | None
    mean_14d: float | None
    total_14d: float | None
    days: list[RadiationDayDTO]
