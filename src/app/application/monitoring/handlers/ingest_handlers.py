from src.app.application.monitoring.services.monitoring_engine import MonitoringEngine
from src.app.application.monitoring.services.presenters import notice_dto
from src.app.shared_kernel.ports.result import Result, ResultDetailed, not_found
from src.vigil_types.monitoring.commands import AlertAckCommand, IngestFrameCommand
from src.vigil_types.monitoring.dto import NoticeDTO


class IngestFrameCommandHandler:
    """Hot path: no DB, no await inside. Bad frames are counted, not errors."""

    def __init__(self, engine: MonitoringEngine) -> None:
        self._engine = engine

    async def __call__(self, message: IngestFrameCommand) -> None:
        self._engine.accept(message.raw)


class AlertAckCommandHandler:
    def __init__(self, engine: MonitoringEngine) -> None:
        self._engine = engine

    async def __call__(self, message: AlertAckCommand) -> ResultDetailed[NoticeDTO]:
        a = self._engine.ack(message.alert_id)
        if a is None:
            return not_found("Open notice not found", field="alert_id")
        return Result.ok(notice_dto(a, self._engine.now_ts(a.crew_id)))
