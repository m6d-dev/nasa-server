from collections.abc import Callable, Coroutine
from typing import Any, Protocol

type EventHandler = Callable[[Any], None]


class EventBusProto(Protocol):
    """In-process and synchronous: subscribers run inline and must not block.
    Anything slow is handed to `TaskSpawnerProto`."""

    def subscribe(self, event_type: type, handler: EventHandler) -> None: ...

    def publish(self, event: Any) -> None: ...

    def publish_many(self, events: list[Any]) -> None: ...


class TaskSpawnerProto(Protocol):
    def spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> None: ...
