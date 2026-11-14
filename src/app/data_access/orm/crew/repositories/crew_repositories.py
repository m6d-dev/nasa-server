from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.application.crew.ports.repositories import (
    CheckinRecord,
    CheckinRepositoryProto,
    CrewInfo,
    CrewRepositoryProto,
)
from src.app.data_access.orm.crew.models.crew_models import CheckinOrmModel, CrewOrmModel
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class CrewOrmRepository(CrewRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_all(self) -> list[CrewInfo]:
        rows = (await self._s.scalars(select(CrewOrmModel).order_by(CrewOrmModel.id))).all()
        return [CrewInfo(r.id, r.name, r.role, r.dev_id, dict(r.share or {})) for r in rows]


def _to_record(r: CheckinOrmModel) -> CheckinRecord:
    return CheckinRecord(
        crew_id=r.crew_id, day=r.day, filed_ts=int(r.filed_ts.timestamp()),
        sleep_q=r.sleep_q, mood=r.mood, energy=r.energy,
        symptoms=tuple(r.symptoms or ()), note=r.note,
    )


class CheckinOrmRepository(CheckinRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, crew_id: int, day: date) -> CheckinRecord | None:
        r = await self._s.get(CheckinOrmModel, (crew_id, day))
        return _to_record(r) if r else None

    async def upsert(self, rec: CheckinRecord) -> None:
        values = dict(
            crew_id=rec.crew_id, day=rec.day, sleep_q=rec.sleep_q, mood=rec.mood,
            energy=rec.energy, symptoms=list(rec.symptoms), note=rec.note,
            filed_ts=datetime.fromtimestamp(rec.filed_ts, tz=UTC),
        )
        stmt = insert(CheckinOrmModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["crew_id", "day"],
            set_={k: stmt.excluded[k] for k in values if k not in ("crew_id", "day")},
        )
        await self._s.execute(stmt)

    async def list_since(self, day: date) -> list[CheckinRecord]:
        rows = (await self._s.scalars(select(CheckinOrmModel).where(CheckinOrmModel.day >= day))).all()
        return [_to_record(r) for r in rows]


ensure_isimplementation(CrewOrmRepository, CrewRepositoryProto)
ensure_isimplementation(CheckinOrmRepository, CheckinRepositoryProto)
