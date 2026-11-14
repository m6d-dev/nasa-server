from dependency_injector import containers, providers

from src.app.application.monitoring.handlers.ingest_handlers import (
    AlertAckCommandHandler,
    IngestFrameCommandHandler,
)
from src.app.application.monitoring.handlers.query_handlers import (
    AlertListQueryHandler,
    CrewListQueryHandler,
    CrewTodayQueryHandler,
    DeviceStatusQueryHandler,
    HealthQueryHandler,
    MetricSeriesQueryHandler,
    SleepQueryHandler,
)
from src.app.application.monitoring.services.facts_adapter import MonitoringFacts
from src.app.application.monitoring.services.monitoring_engine import MonitoringEngine
from src.app.application.monitoring.services.persistence_queue import PersistenceQueue
from src.app.application.monitoring.services.runtime_reset import RuntimeReset
from src.app.application.monitoring.services.sleep_service import SleepService
from src.app.data_access.orm.monitoring.repositories.monitoring_repositories import (
    AggMinuteOrmRepository,
    AlertOrmRepository,
    MaintenanceOrmRepository,
)


class MonitoringDIContainer(containers.DeclarativeContainer):
    config = providers.DependenciesContainer()
    db = providers.DependenciesContainer()
    infra = providers.DependenciesContainer()
    crew = providers.DependenciesContainer()  # filled by root: crew needs our engine
    reporting = providers.DependenciesContainer()  # filled by root: reporting needs our facts

    agg_repo = providers.Factory(AggMinuteOrmRepository, session=db.session)
    alert_repo = providers.Factory(AlertOrmRepository, session=db.session)
    maintenance_repo = providers.Factory(MaintenanceOrmRepository, session=db.session)

    engine = providers.Singleton(
        MonitoringEngine,
        bus=infra.event_bus,
        live=infra.live_hub,
        classifier=infra.pattern_classifier,
        actions=infra.actions,
        link_timeout_s=config.settings.provided.link_timeout_s,
    )
    queue = providers.Singleton(
        PersistenceQueue,
        scope=db.scope,
        uow=db.uow.provider,
        agg_repo=agg_repo.provider,
        alert_repo=alert_repo.provider,
    )
    facts = providers.Singleton(
        MonitoringFacts, engine=engine, queue=queue,
        agg_repo=agg_repo.provider, alert_repo=alert_repo.provider,
    )
    runtime_reset = providers.Singleton(
        RuntimeReset, engine=engine, queue=queue, scope=db.scope,
        uow=db.uow.provider, maintenance=maintenance_repo.provider,
    )
    sleep_service = providers.Factory(SleepService, agg_repo=agg_repo)

    # handlers: always factories, the mediator builds one per message
    ingest_frame_handler = providers.Factory(IngestFrameCommandHandler, engine=engine)
    alert_ack_handler = providers.Factory(AlertAckCommandHandler, engine=engine)
    crew_today_handler = providers.Factory(
        CrewTodayQueryHandler, engine=engine, sleep=sleep_service, checkins=crew.checkin_repo,
        reports=reporting.report_status, radiation=infra.radiation_summary,
        mission_start=config.settings.provided.mission_start,
    )
    crew_list_handler = providers.Factory(
        CrewListQueryHandler, engine=engine, sleep=sleep_service, checkins=crew.checkin_repo
    )
    metric_series_handler = providers.Factory(MetricSeriesQueryHandler, engine=engine, agg_repo=agg_repo)
    alert_list_handler = providers.Factory(AlertListQueryHandler, engine=engine, alert_repo=alert_repo, queue=queue)
    device_status_handler = providers.Factory(DeviceStatusQueryHandler, engine=engine, agg_repo=agg_repo)
    sleep_handler = providers.Factory(SleepQueryHandler, engine=engine, sleep=sleep_service)
    health_handler = providers.Factory(
        HealthQueryHandler, engine=engine, maintenance=maintenance_repo,
        llm_enabled=infra.llm.provided.enabled,
    )
