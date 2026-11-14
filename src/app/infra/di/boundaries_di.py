from dependency_injector import containers, providers

from src.app.application.crew.handlers.checkin_handlers import (
    CheckinFileCommandHandler,
    CheckinGetQueryHandler,
)
from src.app.application.narration.services.narration_service import NarrationService
from src.app.application.radiation.handlers.radiation_handlers import RadiationQueryHandler
from src.app.application.reporting.handlers.report_handlers import (
    ReportGetQueryHandler,
    ReportQueueCommandHandler,
    ReportUpdateCommandHandler,
)
from src.app.application.reporting.services.report_autosave import ReportAutosave
from src.app.application.reporting.services.report_builder import ReportBuilder
from src.app.application.simulation.handlers.sim_handlers import (
    SimResetCommandHandler,
    SimScenarioCommandHandler,
    SimSpeedCommandHandler,
    SimStateQueryHandler,
)
from src.app.data_access.orm.crew.repositories.crew_repositories import (
    CheckinOrmRepository,
    CrewOrmRepository,
)
from src.app.data_access.orm.radiation.repositories.radiation_repositories import RadiationOrmRepository
from src.app.data_access.orm.reporting.repositories.report_repositories import ReportOrmRepository
from src.app.infra.impls.boundary_adapters import ReportStatusAdapter


class CrewDIContainer(containers.DeclarativeContainer):
    db = providers.DependenciesContainer()
    infra = providers.DependenciesContainer()
    monitoring = providers.DependenciesContainer()

    crew_repo = providers.Factory(CrewOrmRepository, session=db.session)
    checkin_repo = providers.Factory(CheckinOrmRepository, session=db.session)

    checkin_get_handler = providers.Factory(
        CheckinGetQueryHandler, clock=monitoring.engine, repo=checkin_repo
    )
    checkin_file_handler = providers.Factory(
        CheckinFileCommandHandler, clock=monitoring.engine, repo=checkin_repo,
        uow=db.uow, bus=infra.event_bus,
    )


class ReportingDIContainer(containers.DeclarativeContainer):
    db = providers.DependenciesContainer()
    monitoring = providers.DependenciesContainer()
    crew = providers.DependenciesContainer()

    report_repo = providers.Factory(ReportOrmRepository, session=db.session)
    builder = providers.Factory(ReportBuilder, facts=monitoring.facts, checkins=crew.checkin_repo)
    report_status = providers.Singleton(ReportStatusAdapter, repo=report_repo.provider)
    autosave = providers.Singleton(
        ReportAutosave, scope=db.scope, uow=db.uow.provider, repo=report_repo.provider,
        builder=builder.provider, facts=monitoring.facts,
    )

    report_get_handler = providers.Factory(
        ReportGetQueryHandler, facts=monitoring.facts, repo=report_repo, builder=builder
    )
    report_update_handler = providers.Factory(
        ReportUpdateCommandHandler, facts=monitoring.facts, repo=report_repo, builder=builder, uow=db.uow
    )
    report_queue_handler = providers.Factory(
        ReportQueueCommandHandler, facts=monitoring.facts, repo=report_repo, builder=builder, uow=db.uow
    )


class RadiationDIContainer(containers.DeclarativeContainer):
    db = providers.DependenciesContainer()

    radiation_repo = providers.Factory(RadiationOrmRepository, session=db.session)
    radiation_handler = providers.Factory(RadiationQueryHandler, repo=radiation_repo)


class SimulationDIContainer(containers.DeclarativeContainer):
    infra = providers.DependenciesContainer()
    monitoring = providers.DependenciesContainer()

    state_handler = providers.Factory(SimStateQueryHandler, vdev=infra.vdev)
    scenario_handler = providers.Factory(SimScenarioCommandHandler, vdev=infra.vdev)
    speed_handler = providers.Factory(SimSpeedCommandHandler, vdev=infra.vdev)
    reset_handler = providers.Factory(SimResetCommandHandler, vdev=infra.vdev, reset=monitoring.runtime_reset)


class NarrationDIContainer(containers.DeclarativeContainer):
    infra = providers.DependenciesContainer()
    monitoring = providers.DependenciesContainer()

    service = providers.Singleton(
        NarrationService, llm=infra.llm, sink=monitoring.engine, tasks=infra.tasks
    )
