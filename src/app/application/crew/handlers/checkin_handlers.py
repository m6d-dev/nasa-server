from src.app.application.crew.ports.repositories import CheckinRecord, CheckinRepositoryProto
from src.app.application.crew.ports.services import CheckinFiled, CrewClockProto
from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto
from src.app.shared_kernel.ports.event import EventBusProto
from src.app.shared_kernel.ports.result import Result, ResultDetailed, invalid, not_found
from src.vigil_types.crew.contracts import CheckinFileCommand, CheckinGetQuery, CheckinViewDTO


def _view(rec: CheckinRecord | None, day: str | None) -> CheckinViewDTO:
    if rec is None:
        return CheckinViewDTO(day=day, filed_ts=None)
    return CheckinViewDTO(
        day=rec.day.isoformat(), filed_ts=rec.filed_ts, sleep_q=rec.sleep_q, mood=rec.mood,
        energy=rec.energy, symptoms=list(rec.symptoms), note=rec.note,
    )


class CheckinGetQueryHandler:
    def __init__(self, clock: CrewClockProto, repo: CheckinRepositoryProto) -> None:
        self._clock, self._repo = clock, repo

    async def __call__(self, message: CheckinGetQuery) -> ResultDetailed[CheckinViewDTO]:
        if not self._clock.has_crew(message.crew_id):
            return not_found("Crew member not found", field="crew_id")
        today = self._clock.today(message.crew_id)
        rec = await self._repo.get(message.crew_id, today) if today else None
        return Result.ok(_view(rec, today.isoformat() if today else None))


class CheckinFileCommandHandler:
    """The check-in belongs to the person's virtual day, not the server's."""

    def __init__(self, clock: CrewClockProto, repo: CheckinRepositoryProto,
                 uow: UnitOfWorkProto, bus: EventBusProto) -> None:
        self._clock, self._repo, self._uow, self._bus = clock, repo, uow, bus

    async def __call__(self, message: CheckinFileCommand) -> ResultDetailed[CheckinViewDTO]:
        cid = message.crew_id
        if not self._clock.has_crew(cid):
            return not_found("Crew member not found", field="crew_id")
        today, now = self._clock.today(cid), self._clock.now_ts(cid)
        if today is None or now is None:
            return invalid("No device data yet: the virtual date is unknown", field="crew_id")
        rec = CheckinRecord(
            crew_id=cid, day=today, filed_ts=now, sleep_q=message.sleep_q, mood=message.mood,
            energy=message.energy, symptoms=tuple(dict.fromkeys(message.symptoms)), note=message.note,
        )
        async with self._uow:
            await self._repo.upsert(rec)
        self._bus.publish(CheckinFiled(cid, today, rec.symptoms))
        return Result.ok(_view(rec, today.isoformat()))
