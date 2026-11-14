from litestar import Controller, get

from src.app.shared_kernel.ports.mediator import MediatorProto
from src.vigil_types.radiation.contracts import RadiationDTO, RadiationQuery


class RadiationController(Controller):
    path = "/radiation"
    tags = ["radiation"]

    @get("")
    async def radiation(self, mediator: MediatorProto) -> RadiationDTO:
        return await mediator.ask(RadiationQuery())
