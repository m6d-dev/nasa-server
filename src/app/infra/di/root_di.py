from dependency_injector import containers, providers

from src.app.infra.di.boundaries_di import (
    CrewDIContainer,
    NarrationDIContainer,
    RadiationDIContainer,
    ReportingDIContainer,
    SimulationDIContainer,
)
from src.app.infra.di.core_di import ConfigDIContainer, DatabaseDIContainer, InfraDIContainer
from src.app.infra.di.monitoring_di import MonitoringDIContainer


class RootDIContainer(containers.DeclarativeContainer):
    """Wiring order: config → db → infra → monitoring → crew → reporting →
    radiation → simulation → narration. Two cycles are closed in `build()`."""

    config = providers.Container(ConfigDIContainer)
    db = providers.Container(DatabaseDIContainer, config=config)
    infra = providers.Container(InfraDIContainer, config=config)
    monitoring = providers.Container(MonitoringDIContainer, config=config, db=db, infra=infra)
    crew = providers.Container(CrewDIContainer, db=db, infra=infra, monitoring=monitoring)
    reporting = providers.Container(ReportingDIContainer, db=db, monitoring=monitoring, crew=crew)
    radiation = providers.Container(RadiationDIContainer, db=db)
    simulation = providers.Container(SimulationDIContainer, infra=infra, monitoring=monitoring)
    narration = providers.Container(NarrationDIContainer, infra=infra, monitoring=monitoring)


def build() -> RootDIContainer:
    root = RootDIContainer()
    # monitoring's Today needs crew's check-ins and reporting's queue status,
    # both of which are built on top of monitoring
    root.monitoring.crew.override(root.crew)
    root.monitoring.reporting.override(root.reporting)
    return root
