"""Message ↔ handler wiring, per boundary, with the policy visible at each line.

DI says how to build a handler; this says which message it answers. A handler
built but not registered here is unreachable.
"""

from src.app.infra.di.root_di import RootDIContainer
from src.app.shared_kernel.ports.mediator import MediatorProto
from src.app.shared_kernel.types.cqrs import DEVICE_POINT, PUBLIC_POINT
from src.vigil_types.crew.contracts import CheckinFileCommand, CheckinGetQuery
from src.vigil_types.monitoring.commands import AlertAckCommand, IngestFrameCommand
from src.vigil_types.monitoring.queries import (
    AlertListQuery,
    CrewListQuery,
    CrewTodayQuery,
    DeviceStatusQuery,
    HealthQuery,
    MetricSeriesQuery,
    SleepQuery,
)
from src.vigil_types.radiation.contracts import RadiationQuery
from src.vigil_types.reporting.contracts import (
    ReportGetQuery,
    ReportQueueCommand,
    ReportUpdateCommand,
)
from src.vigil_types.simulation.contracts import (
    SimResetCommand,
    SimScenarioCommand,
    SimSpeedCommand,
    SimStateQuery,
)


def register_monitoring(m: MediatorProto, c: RootDIContainer) -> None:
    mon = c.monitoring
    m.register_command(IngestFrameCommand, mon.ingest_frame_handler, policy=DEVICE_POINT)
    m.register_command(AlertAckCommand, mon.alert_ack_handler, policy=PUBLIC_POINT)
    m.register_query(CrewListQuery, mon.crew_list_handler, policy=PUBLIC_POINT)
    m.register_query(CrewTodayQuery, mon.crew_today_handler, policy=PUBLIC_POINT)
    m.register_query(MetricSeriesQuery, mon.metric_series_handler, policy=PUBLIC_POINT)
    m.register_query(AlertListQuery, mon.alert_list_handler, policy=PUBLIC_POINT)
    m.register_query(DeviceStatusQuery, mon.device_status_handler, policy=PUBLIC_POINT)
    m.register_query(SleepQuery, mon.sleep_handler, policy=PUBLIC_POINT)
    m.register_query(HealthQuery, mon.health_handler, policy=PUBLIC_POINT)


def register_crew(m: MediatorProto, c: RootDIContainer) -> None:
    m.register_query(CheckinGetQuery, c.crew.checkin_get_handler, policy=PUBLIC_POINT)
    m.register_command(CheckinFileCommand, c.crew.checkin_file_handler, policy=PUBLIC_POINT)


def register_reporting(m: MediatorProto, c: RootDIContainer) -> None:
    m.register_query(ReportGetQuery, c.reporting.report_get_handler, policy=PUBLIC_POINT)
    m.register_command(ReportUpdateCommand, c.reporting.report_update_handler, policy=PUBLIC_POINT)
    m.register_command(ReportQueueCommand, c.reporting.report_queue_handler, policy=PUBLIC_POINT)


def register_radiation(m: MediatorProto, c: RootDIContainer) -> None:
    m.register_query(RadiationQuery, c.radiation.radiation_handler, policy=PUBLIC_POINT)


def register_simulation(m: MediatorProto, c: RootDIContainer) -> None:
    sim = c.simulation
    m.register_query(SimStateQuery, sim.state_handler, policy=PUBLIC_POINT)
    m.register_command(SimScenarioCommand, sim.scenario_handler, policy=PUBLIC_POINT)
    m.register_command(SimSpeedCommand, sim.speed_handler, policy=PUBLIC_POINT)
    m.register_command(SimResetCommand, sim.reset_handler, policy=PUBLIC_POINT)


def register_all(c: RootDIContainer) -> MediatorProto:
    m: MediatorProto = c.infra.mediator()
    for fn in (register_monitoring, register_crew, register_reporting, register_radiation, register_simulation):
        fn(m, c)
    return m
