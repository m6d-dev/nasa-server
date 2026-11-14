import asyncio
import logging
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any

from src.app.shared_kernel.ports.event import EventBusProto, EventHandler, TaskSpawnerProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

logger = logging.getLogger("vigil.bus")


class InProcessEventBus(EventBusProto):
    def __init__(self) -> None:
        self._subs: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._subs[event_type].append(handler)

    def publish(self, event: Any) -> None:
        for h in self._subs.get(type(event), ()):
            try:
                h(event)
            except Exception:  # noqa: BLE001 - one bad subscriber must not stop ingest
                logger.exception("subscriber failed for %s", type(event).__name__)

    def publish_many(self, events: list[Any]) -> None:
        for e in events:
            self.publish(e)


class AsyncioTaskSpawner(TaskSpawnerProto):
    """Keeps references so tasks are not garbage-collected mid-flight."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> None:
        t = asyncio.get_running_loop().create_task(coro, name=name)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)


ensure_isimplementation(InProcessEventBus, EventBusProto)
ensure_isimplementation(AsyncioTaskSpawner, TaskSpawnerProto)
