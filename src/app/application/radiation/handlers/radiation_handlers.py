from typing import Any

from src.app.application.monitoring.ports.services import RadiationSummaryProto
from src.app.application.radiation.ports.repositories import RadiationDay, RadiationRepositoryProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation
from src.vigil_types.radiation.contracts import RadiationDayDTO, RadiationDTO, RadiationQuery

LAST_DAYS = 14


def summarize(days: list[RadiationDay]) -> RadiationDTO:
    last = days[-LAST_DAYS:]
    doses = [d.dose for d in last]
    return RadiationDTO(
        unit=last[0].unit if last else "mGy",
        instrument=last[0].instrument if last else None,
        last_24h=doses[-1] if doses else None,
        mean_14d=round(sum(doses) / len(doses), 4) if doses else None,
        total_14d=round(sum(doses), 4) if doses else None,
        days=[RadiationDayDTO(day=d.day.isoformat(), dose=d.dose) for d in last],
    )


class RadiationQueryHandler:
    def __init__(self, repo: RadiationRepositoryProto) -> None:
        self._repo = repo

    async def __call__(self, message: RadiationQuery) -> RadiationDTO:
        return summarize(await self._repo.list_all())


class RadiationSummary(RadiationSummaryProto):
    """Port for the Today screen; days are cached at start, the file is static."""

    def __init__(self) -> None:
        self.days: list[RadiationDay] = []

    async def last_24h(self) -> dict[str, Any] | None:
        if not self.days:
            return None
        d = self.days[-1]
        return {"dose": d.dose, "unit": d.unit, "day": d.day.isoformat()}


ensure_isimplementation(RadiationSummary, RadiationSummaryProto)
