from datetime import UTC, date, datetime

from src.app.application.reporting.ports.repositories import ReportRecord, ReportRepositoryProto
from src.app.application.reporting.ports.sources import MonitoringFactsProto
from src.app.application.reporting.services.report_builder import ReportBuilder
from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto
from src.app.shared_kernel.ports.result import Result, ResultDetailed, invalid, not_found
from src.vigil_types.reporting.contracts import (
    ReportDTO,
    ReportGetQuery,
    ReportQueueCommand,
    ReportUpdateCommand,
)


def _parse_day(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _dto(rec: ReportRecord) -> ReportDTO:
    return ReportDTO(day=rec.day.isoformat(), crew=rec.crew_id, queued_ts=rec.queued_ts,
                     include=rec.include, note=rec.note or "", body=rec.body)


class _ReportBase:
    def __init__(self, facts: MonitoringFactsProto, repo: ReportRepositoryProto, builder: ReportBuilder) -> None:
        self._facts, self._repo, self._builder = facts, repo, builder

    def _today(self, crew_id: int) -> date | None:
        now = self._facts.now_ts(crew_id)
        return None if now is None else datetime.fromtimestamp(now, tz=UTC).date()

    async def _current(self, crew_id: int, d: date) -> ReportRecord:
        """A saved past day is returned as saved; today is rebuilt (partial) every time."""
        saved = await self._repo.get(crew_id, d)
        if saved is not None and d != self._today(crew_id):
            return saved
        return await self._builder.build(crew_id, d, saved)

    def _check(self, crew_id: int, day: str) -> ResultDetailed[date]:
        if not self._facts.has_crew(crew_id):
            return not_found("Crew member not found", field="crew_id")
        d = _parse_day(day)
        if d is None:
            return invalid("Invalid date", field="day")
        return Result.ok(d)


class ReportGetQueryHandler(_ReportBase):
    async def __call__(self, message: ReportGetQuery) -> ResultDetailed[ReportDTO]:
        chk = self._check(message.crew_id, message.day)
        if chk.is_err():
            return Result.err(chk.unwrap_err())
        return Result.ok(_dto(await self._current(message.crew_id, chk.unwrap())))


class ReportUpdateCommandHandler(_ReportBase):
    def __init__(self, facts, repo, builder, uow: UnitOfWorkProto) -> None:
        super().__init__(facts, repo, builder)
        self._uow = uow

    async def __call__(self, message: ReportUpdateCommand) -> ResultDetailed[ReportDTO]:
        chk = self._check(message.crew_id, message.day)
        if chk.is_err():
            return Result.err(chk.unwrap_err())
        rec = await self._current(message.crew_id, chk.unwrap())
        if message.include is not None:
            rec.include = {**rec.include, **message.include}
        if message.note is not None:
            rec.note = message.note
        async with self._uow:
            await self._repo.save(rec)
        return Result.ok(_dto(rec))


class ReportQueueCommandHandler(_ReportBase):
    """Sending = queued until the next comms pass (PLAN §9.9)."""

    def __init__(self, facts, repo, builder, uow: UnitOfWorkProto) -> None:
        super().__init__(facts, repo, builder)
        self._uow = uow

    async def __call__(self, message: ReportQueueCommand) -> ResultDetailed[ReportDTO]:
        chk = self._check(message.crew_id, message.day)
        if chk.is_err():
            return Result.err(chk.unwrap_err())
        rec = await self._current(message.crew_id, chk.unwrap())
        rec.queued_ts = self._facts.now_ts(message.crew_id)
        async with self._uow:
            await self._repo.save(rec)
        return Result.ok(_dto(rec))
