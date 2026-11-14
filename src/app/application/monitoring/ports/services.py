from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import date
from typing import Any, Protocol

from src.app.application.crew.ports.repositories import CheckinRecord
from src.app.domain.monitoring.entities.alert import AlertEntity


class LiveBroadcasterProto(Protocol):
    """`/live?crew=` fan-out. Never blocks the pipeline; slow clients lose messages."""

    def publish(self, crew_id: int, message: dict[str, Any]) -> None: ...


class PersistenceQueueProto(Protocol):
    """Write-behind for agg_1m and alert: the pipeline never waits on Postgres (§13)."""

    def enqueue_minute(self, row: dict[str, Any]) -> None: ...

    def enqueue_alert(self, alert: AlertEntity) -> None: ...

    async def flush(self, timeout: float = 10.0) -> bool: ...

    def clear(self) -> None: ...


# opens a DB scope for background work (no HTTP request around it)
type DbScopeFactory = Callable[[], AbstractAsyncContextManager[Any]]


class CheckinReaderProto(Protocol):
    """Port onto the crew boundary; bound to its repository in DI."""

    async def get(self, crew_id: int, day: date) -> CheckinRecord | None: ...

    async def list_since(self, day: date) -> list[CheckinRecord]: ...


class ReportStatusProto(Protocol):
    async def queued_ts(self, crew_id: int, day: date) -> int | None: ...


class RadiationSummaryProto(Protocol):
    async def last_24h(self) -> dict[str, Any] | None: ...
