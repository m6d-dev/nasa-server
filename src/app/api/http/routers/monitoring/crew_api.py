from typing import Annotated

from litestar import Controller, get, post
from litestar.params import Parameter

from src.app.shared_kernel.ports.mediator import MediatorProto
from src.app.shared_kernel.ports.result import ResultDetailed
from src.vigil_types.monitoring.commands import AlertAckCommand
from src.vigil_types.monitoring.dto import (
    CrewRowDTO,
    DeviceDTO,
    HealthDTO,
    MetricSeriesDTO,
    NoticeDTO,
    SleepDTO,
    TodayDTO,
)
from src.vigil_types.monitoring.queries import (
    AlertListQuery,
    CrewListQuery,
    CrewTodayQuery,
    DeviceStatusQuery,
    HealthQuery,
    MetricSeriesQuery,
    SleepQuery,
)


def _unwrap[T](res: ResultDetailed[T]) -> T:
    if res.is_err():
        raise res.as_app_exception()
    return res.unwrap()


class CrewMonitoringController(Controller):
    path = "/crew"
    tags = ["crew"]

    @get("")
    async def list_crew(self, mediator: MediatorProto) -> list[CrewRowDTO]:
        return await mediator.ask(CrewListQuery())

    @get("/{crew_id:int}/today")
    async def today(self, crew_id: int, mediator: MediatorProto) -> TodayDTO:
        return _unwrap(await mediator.ask(CrewTodayQuery(crew_id=crew_id)))

    @get("/{crew_id:int}/metric/{m:str}")
    async def metric(
        self, crew_id: int, m: str, mediator: MediatorProto,
        range_: Annotated[str, Parameter(query="range")] = "1h",
    ) -> MetricSeriesDTO:
        # m and range are validated by the query model, not by Litestar
        q = MetricSeriesQuery(crew_id=crew_id, m=m, range=range_)  # type: ignore[arg-type]
        return _unwrap(await mediator.ask(q))

    @get("/{crew_id:int}/alerts")
    async def alerts(
        self, crew_id: int, mediator: MediatorProto,
        open_: Annotated[int, Parameter(query="open", ge=0, le=1)] = 0,
    ) -> list[NoticeDTO]:
        return _unwrap(await mediator.ask(AlertListQuery(crew_id=crew_id, open_only=bool(open_))))

    @get("/{crew_id:int}/device")
    async def device(self, crew_id: int, mediator: MediatorProto) -> DeviceDTO:
        return _unwrap(await mediator.ask(DeviceStatusQuery(crew_id=crew_id)))

    @get("/{crew_id:int}/sleep")
    async def sleep(self, crew_id: int, mediator: MediatorProto) -> SleepDTO:
        return _unwrap(await mediator.ask(SleepQuery(crew_id=crew_id)))


class AlertController(Controller):
    path = "/alerts"
    tags = ["alerts"]

    @post("/{alert_id:int}/ack", status_code=200)
    async def ack(self, alert_id: int, mediator: MediatorProto) -> NoticeDTO:
        return _unwrap(await mediator.send(AlertAckCommand(alert_id=alert_id)))


class HealthController(Controller):
    path = "/health"
    tags = ["health"]

    @get("")
    async def health(self, mediator: MediatorProto) -> HealthDTO:
        return await mediator.ask(HealthQuery())

