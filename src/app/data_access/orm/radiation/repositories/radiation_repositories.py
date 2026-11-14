from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.application.radiation.ports.repositories import RadiationDay, RadiationRepositoryProto
from src.app.data_access.orm.radiation.models.radiation_models import RadiationDailyOrmModel
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class RadiationOrmRepository(RadiationRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def replace_all(self, days: list[RadiationDay]) -> None:
        await self._s.execute(delete(RadiationDailyOrmModel))
        if days:
            self._s.add_all(
                RadiationDailyOrmModel(day=d.day, dose=d.dose, unit=d.unit, instrument=d.instrument)
                for d in days
            )

    async def list_all(self) -> list[RadiationDay]:
        rows = (await self._s.scalars(select(RadiationDailyOrmModel).order_by(RadiationDailyOrmModel.day))).all()
        # `real` comes back as 0.15379999577…; the file had 4 decimals
        return [RadiationDay(r.day, round(r.dose, 4), r.unit, r.instrument) for r in rows]


ensure_isimplementation(RadiationOrmRepository, RadiationRepositoryProto)
