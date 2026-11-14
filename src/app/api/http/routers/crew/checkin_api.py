from litestar import Controller, get, post

from src.app.api.http.routers.monitoring.crew_api import _unwrap
from src.app.shared_kernel.ports.mediator import MediatorProto
from src.vigil_types.crew.contracts import (
    CheckinDTO,
    CheckinFileCommand,
    CheckinGetQuery,
    CheckinViewDTO,
)


class CheckinController(Controller):
    path = "/crew/{crew_id:int}/checkin"
    tags = ["checkin"]

    @get("")
    async def get_checkin(self, crew_id: int, mediator: MediatorProto) -> CheckinViewDTO:
        return _unwrap(await mediator.ask(CheckinGetQuery(crew_id=crew_id)))

    @post("", status_code=200)
    async def file_checkin(self, crew_id: int, data: CheckinDTO, mediator: MediatorProto) -> CheckinViewDTO:
        cmd = CheckinFileCommand(crew_id=crew_id, **data.model_dump())
        return _unwrap(await mediator.send(cmd))
