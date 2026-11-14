from litestar import Controller, get, post, put

from src.app.api.http.routers.monitoring.crew_api import _unwrap
from src.app.shared_kernel.ports.mediator import MediatorProto
from src.vigil_types.reporting.contracts import (
    ReportDTO,
    ReportGetQuery,
    ReportQueueCommand,
    ReportUpdateCommand,
    ReportUpdateDTO,
)


class ReportController(Controller):
    path = "/crew/{crew_id:int}/report/{day:str}"
    tags = ["report"]

    @get("")
    async def get_report(self, crew_id: int, day: str, mediator: MediatorProto) -> ReportDTO:
        return _unwrap(await mediator.ask(ReportGetQuery(crew_id=crew_id, day=day)))

    @put("")
    async def update_report(self, crew_id: int, day: str, data: ReportUpdateDTO, mediator: MediatorProto) -> ReportDTO:
        cmd = ReportUpdateCommand(crew_id=crew_id, day=day, **data.model_dump())
        return _unwrap(await mediator.send(cmd))

    @post("/queue", status_code=200)
    async def queue_report(self, crew_id: int, day: str, mediator: MediatorProto) -> ReportDTO:
        return _unwrap(await mediator.send(ReportQueueCommand(crew_id=crew_id, day=day)))
