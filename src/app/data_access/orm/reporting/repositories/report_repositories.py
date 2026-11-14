from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.application.reporting.ports.repositories import ReportRecord, ReportRepositoryProto
from src.app.data_access.orm.reporting.models.report_models import ReportOrmModel
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class ReportOrmRepository(ReportRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, crew_id: int, day: date) -> ReportRecord | None:
        r = await self._s.get(ReportOrmModel, (crew_id, day))
        if r is None:
            return None
        return ReportRecord(
            crew_id=r.crew_id, day=r.day, body=dict(r.body), include=dict(r.include), note=r.note,
            queued_ts=int(r.queued_ts.timestamp()) if r.queued_ts else None,
        )

    async def save(self, rec: ReportRecord) -> None:
        values = dict(
            crew_id=rec.crew_id, day=rec.day, body=rec.body, include=rec.include, note=rec.note,
            queued_ts=datetime.fromtimestamp(rec.queued_ts, tz=UTC) if rec.queued_ts else None,
        )
        stmt = insert(ReportOrmModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["crew_id", "day"],
            set_={k: stmt.excluded[k] for k in ("body", "include", "note", "queued_ts")},
        )
        await self._s.execute(stmt)


ensure_isimplementation(ReportOrmRepository, ReportRepositoryProto)
