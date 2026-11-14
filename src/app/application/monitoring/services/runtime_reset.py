from collections.abc import Callable

from src.app.application.monitoring.ports.repositories import MaintenanceRepositoryProto
from src.app.application.monitoring.ports.services import DbScopeFactory, PersistenceQueueProto
from src.app.application.monitoring.services.monitoring_engine import MonitoringEngine
from src.app.application.simulation.ports.services import RuntimeResetProto
from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation


class RuntimeReset(RuntimeResetProto):
    def __init__(
        self,
        engine: MonitoringEngine,
        queue: PersistenceQueueProto,
        scope: DbScopeFactory,
        uow: Callable[[], UnitOfWorkProto],
        maintenance: Callable[[], MaintenanceRepositoryProto],
    ) -> None:
        self._engine, self._queue, self._scope, self._uow, self._maint = engine, queue, scope, uow, maintenance

    async def reset_all(self) -> None:
        self._queue.clear()
        self._engine.reset()
        await self._queue.flush(5.0)  # a batch already in flight must land before truncate
        async with self._scope():
            async with self._uow():
                await self._maint().truncate_runtime()


ensure_isimplementation(RuntimeReset, RuntimeResetProto)
