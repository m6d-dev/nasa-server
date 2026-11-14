from typing import Any

from litestar import Controller, MediaType, Response, get, post

from src.app.shared_kernel.ports.mediator import MediatorProto
from src.app.shared_kernel.ports.result import ResultDetailed
from src.vigil_types.simulation.contracts import (
    SimResetCommand,
    SimResponse,
    SimScenarioCommand,
    SimSpeedCommand,
    SimStateQuery,
)


def _passthrough(res: ResultDetailed[SimResponse]) -> Response[Any]:
    """vdev's answer as is, status included (§11.10)."""
    if res.is_err():
        raise res.as_app_exception()
    r = res.unwrap()
    return Response(r.body, status_code=r.status, media_type=MediaType.JSON)


class SimController(Controller):
    path = "/sim"
    tags = ["sim"]

    @get("/state")
    async def state(self, mediator: MediatorProto) -> Response[Any]:
        return _passthrough(await mediator.ask(SimStateQuery()))

    @post("/scenario")
    async def scenario(self, data: SimScenarioCommand, mediator: MediatorProto) -> Response[Any]:
        return _passthrough(await mediator.send(data))

    @post("/speed")
    async def speed(self, data: SimSpeedCommand, mediator: MediatorProto) -> Response[Any]:
        return _passthrough(await mediator.send(data))

    @post("/reset")
    async def reset(self, mediator: MediatorProto) -> Response[Any]:
        return _passthrough(await mediator.send(SimResetCommand()))
