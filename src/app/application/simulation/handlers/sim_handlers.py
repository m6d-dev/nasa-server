from src.app.application.simulation.ports.services import RuntimeResetProto, VdevClientProto
from src.app.shared_kernel.ports.result import Result, ResultDetailed, unavailable
from src.vigil_types.simulation.contracts import (
    SimResetCommand,
    SimResponse,
    SimScenarioCommand,
    SimSpeedCommand,
    SimStateQuery,
)

VDEV_DOWN = "Virtual device is unreachable"


async def _forward(vdev: VdevClientProto, method: str, path: str, body: dict | None) -> ResultDetailed[SimResponse]:
    res = await vdev.request(method, path, body)
    if res is None:
        return unavailable(VDEV_DOWN)
    return Result.ok(SimResponse(status=res[0], body=res[1]))


class SimStateQueryHandler:
    def __init__(self, vdev: VdevClientProto) -> None:
        self._vdev = vdev

    async def __call__(self, message: SimStateQuery) -> ResultDetailed[SimResponse]:
        return await _forward(self._vdev, "GET", "/state", None)


class SimScenarioCommandHandler:
    def __init__(self, vdev: VdevClientProto) -> None:
        self._vdev = vdev

    async def __call__(self, message: SimScenarioCommand) -> ResultDetailed[SimResponse]:
        return await _forward(self._vdev, "POST", "/scenario", message.model_dump(exclude_none=True))


class SimSpeedCommandHandler:
    def __init__(self, vdev: VdevClientProto) -> None:
        self._vdev = vdev

    async def __call__(self, message: SimSpeedCommand) -> ResultDetailed[SimResponse]:
        return await _forward(self._vdev, "POST", "/speed", message.model_dump(exclude_none=True))


class SimResetCommandHandler:
    """vdev first, so no frame of the old run lands in the cleared state."""

    def __init__(self, vdev: VdevClientProto, reset: RuntimeResetProto) -> None:
        self._vdev, self._reset = vdev, reset

    async def __call__(self, message: SimResetCommand) -> ResultDetailed[SimResponse]:
        res = await self._vdev.request("POST", "/reset", {})
        await self._reset.reset_all()  # cleared even if vdev is down
        if res is None:
            return unavailable(VDEV_DOWN)
        return Result.ok(SimResponse(status=res[0], body=res[1]))
