"""Small adapters where one boundary's port is served by another boundary's
repository. Infra is the only layer allowed to see both sides."""

from collections.abc import Callable
from datetime import date

from src.app.application.monitoring.ports.services import ReportStatusProto
from src.app.application.reporting.ports.repositories import ReportRepositoryProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class ReportStatusAdapter(ReportStatusProto):
    def __init__(self, repo: Callable[[], ReportRepositoryProto]) -> None:
        self._repo = repo

    async def queued_ts(self, crew_id: int, day: date) -> int | None:
        rec = await self._repo().get(crew_id, day)
        return rec.queued_ts if rec else None


ensure_isimplementation(ReportStatusAdapter, ReportStatusProto)
