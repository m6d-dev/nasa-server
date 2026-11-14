import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from src.app.application.monitoring.ports.services import DbScopeFactory
from src.app.application.reporting.ports.repositories import ReportRepositoryProto
from src.app.application.reporting.ports.sources import MonitoringFactsProto
from src.app.application.reporting.services.report_builder import ReportBuilder
from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto

logger = logging.getLogger("vigil.report")


class ReportAutosave:
    """Saves the finished day when a person's virtual day turns over (§11.8)."""

    def __init__(
        self,
        scope: DbScopeFactory,
        uow: Callable[[], UnitOfWorkProto],
        repo: Callable[[], ReportRepositoryProto],
        builder: Callable[[], ReportBuilder],
        facts: MonitoringFactsProto,
    ) -> None:
        self._scope, self._uow, self._repo, self._builder, self._facts = scope, uow, repo, builder, facts
        # history replay turns ~100 days over in seconds; one save at a time
        self._lock = asyncio.Lock()

    async def save_day(self, crew_id: int, day_number: int) -> None:
        d = datetime.fromtimestamp(day_number * 86400, tz=UTC).date()
        async with self._lock:
            await self._save(crew_id, d)

    async def _save(self, crew_id: int, d) -> None:
        try:
            await self._facts.flush()  # the day's minutes must be in the table first
            async with self._scope():
                repo = self._repo()
                rec = await self._builder().build(crew_id, d, await repo.get(crew_id, d))
                async with self._uow():
                    await repo.save(rec)
        except Exception:  # noqa: BLE001 - a missed autosave is rebuilt on GET
            logger.exception("report autosave failed crew=%s day=%s", crew_id, d)
