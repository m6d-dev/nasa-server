from functools import partial

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.application.cqrs.mediator import Mediator
from src.app.application.radiation.handlers.radiation_handlers import RadiationSummary
from src.app.data_access.orm.unit_of_work import OrmUnitOfWork, current_session, db_scope
from src.app.infra.impls.event_bus import AsyncioTaskSpawner, InProcessEventBus
from src.app.infra.impls.http_clients import OllamaClient, VdevClient
from src.app.infra.impls.live_hub import LiveHub
from src.app.infra.impls.model_files import load_actions, load_pattern_classifier
from src.app.shared_kernel.config.app_config import AppConfig


class ConfigDIContainer(containers.DeclarativeContainer):
    settings: providers.Singleton[AppConfig] = providers.Singleton(AppConfig)


class DatabaseDIContainer(containers.DeclarativeContainer):
    config = providers.DependenciesContainer()

    engine = providers.Singleton(
        lambda cfg: create_async_engine(cfg.db.url, pool_pre_ping=True, pool_size=10),
        cfg=config.settings,
    )
    session_factory = providers.Singleton(
        async_sessionmaker, bind=engine, autoflush=False, expire_on_commit=False, class_=AsyncSession
    )
    # the session of the current scope (HTTP request or background job)
    session = providers.Callable(current_session)
    uow = providers.Factory(OrmUnitOfWork, session=session)
    # zero-arg callable opening a new scope, for background work
    scope = providers.Singleton(partial, db_scope, session_factory)


class InfraDIContainer(containers.DeclarativeContainer):
    config = providers.DependenciesContainer()

    mediator = providers.Singleton(Mediator)
    event_bus = providers.Singleton(InProcessEventBus)
    tasks = providers.Singleton(AsyncioTaskSpawner)
    live_hub = providers.Singleton(LiveHub)
    llm = providers.Singleton(
        lambda c: OllamaClient(c.ollama_url, c.ollama_model, c.llm_timeout_s), c=config.settings
    )
    vdev = providers.Singleton(lambda c: VdevClient(c.vdev_url), c=config.settings)
    pattern_classifier = providers.Singleton(
        lambda c: load_pattern_classifier(c.pattern_model, c.pattern_meta), c=config.settings
    )
    actions = providers.Singleton(lambda c: load_actions(c.actions_file), c=config.settings)
    radiation_summary = providers.Singleton(RadiationSummary)
