"""Write-behind for agg_1m and alert (BACKEND_TZ §10, §13).

Live: a row per minute, written as soon as it arrives. History replay: batches
of up to 1000 via COPY. If Postgres is down, rows stay in memory and the write
is retried every second; ingest never waits.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from src.app.application.monitoring.ports.repositories import (
    AggMinuteRepositoryProto,
    AlertRepositoryProto,
)
from src.app.application.monitoring.ports.services import DbScopeFactory, PersistenceQueueProto
from src.app.domain.monitoring.entities.alert import AlertEntity
from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

logger = logging.getLogger("vigil.writer")
BATCH = 1000
RETRY_S = 1.0


class PersistenceQueue(PersistenceQueueProto):
    def __init__(
        self,
        scope: DbScopeFactory,
        uow: Callable[[], UnitOfWorkProto],
        agg_repo: Callable[[], AggMinuteRepositoryProto],
        alert_repo: Callable[[], AlertRepositoryProto],
    ) -> None:
        self._scope, self._uow, self._agg_repo, self._alert_repo = scope, uow, agg_repo, alert_repo
        self._rows: list[dict[str, Any]] = []
        self._alerts: dict[int, AlertEntity] = {}
        self._wake = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._task: asyncio.Task | None = None

    def enqueue_minute(self, row: dict[str, Any]) -> None:
        self._rows.append(row)
        self._idle.clear()
        self._wake.set()

    def enqueue_alert(self, alert: AlertEntity) -> None:
        self._alerts[alert.id] = alert  # type: ignore[index]  # latest state wins
        self._idle.clear()
        self._wake.set()

    async def flush(self, timeout: float = 10.0) -> bool:
        try:
            await asyncio.wait_for(self._idle.wait(), timeout)
            return True
        except TimeoutError:
            return False

    def clear(self) -> None:
        self._rows.clear()
        self._alerts.clear()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="persistence-queue")

    async def stop(self) -> None:
        await self.flush(5.0)
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._rows or self._alerts:
                rows, self._rows = self._rows[:BATCH], self._rows[BATCH:]
                alerts, self._alerts = list(self._alerts.values()), {}
                try:
                    async with self._scope():
                        async with self._uow():
                            await self._agg_repo().insert_many(rows)
                            # alerts after minutes: an alert row never points past its data
                            await self._alert_repo().upsert_many(alerts)
                except Exception as exc:  # noqa: BLE001 - keep the data, retry
                    logger.warning("db write failed (%s rows, %s alerts): %s", len(rows), len(alerts), exc)
                    self._rows[:0] = rows
                    for a in alerts:
                        self._alerts.setdefault(a.id, a)  # type: ignore[arg-type]
                    await asyncio.sleep(RETRY_S)
                await asyncio.sleep(0)  # let ingest run between batches
            self._idle.set()


ensure_isimplementation(PersistenceQueue, PersistenceQueueProto)
