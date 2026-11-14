from collections.abc import Callable
from datetime import date
from typing import Any

from src.app.application.monitoring.ports.repositories import (
    AggMinuteRepositoryProto,
    AlertRepositoryProto,
)
from src.app.application.monitoring.ports.services import PersistenceQueueProto
from src.app.application.monitoring.services.monitoring_engine import MonitoringEngine
from src.app.application.reporting.ports.sources import IncidentFact, MonitoringFactsProto, NightFact
from src.app.domain.monitoring.services.sleep import find_night, night_window
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class MonitoringFacts(MonitoringFactsProto):
    """Monitoring's answer to reporting's port: the boundary crossing is here, typed."""

    def __init__(
        self,
        engine: MonitoringEngine,
        queue: PersistenceQueueProto,
        agg_repo: Callable[[], AggMinuteRepositoryProto],
        alert_repo: Callable[[], AlertRepositoryProto],
    ) -> None:
        self._engine, self._queue, self._agg_repo, self._alert_repo = engine, queue, agg_repo, alert_repo

    def has_crew(self, crew_id: int) -> bool:
        return self._engine.has_crew(crew_id)

    def now_ts(self, crew_id: int) -> int | None:
        return self._engine.now_ts(crew_id)

    def baseline_state(self, crew_id: int) -> str:
        return self._engine.aggregates[crew_id].learn.state

    async def flush(self) -> None:
        await self._queue.flush(30.0)

    async def minute_rows(self, crew_id: int, start_ts: int, end_ts: int) -> list[dict[str, Any]]:
        return await self._agg_repo().rows(crew_id, start_ts, end_ts)

    async def incidents(self, crew_id: int, start_ts: int, end_ts: int) -> list[IncidentFact]:
        items = await self._alert_repo().list_since(start_ts)
        return [
            IncidentFact(a.ts_start, a.ts_end, a.peak_level, a.pattern, a.ack_ts is not None)
            for a in items
            if a.crew_id == crew_id and a.is_incident and a.ts_start < end_ts
        ]

    async def night(self, crew_id: int, day: date) -> NightFact:
        lo, hi = night_window(day)
        n = find_night(day, await self._agg_repo().ctx_rows(crew_id, lo, hi))
        return NightFact(n.minutes, n.onset_ts)


ensure_isimplementation(MonitoringFacts, MonitoringFactsProto)
