import asyncio
import json
from collections import defaultdict
from typing import Any

from src.app.application.monitoring.ports.services import LiveBroadcasterProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

QUEUE_MAX = 256


class LiveHub(LiveBroadcasterProto):
    """One bounded queue per `/live` connection. A full queue drops the message:
    the pipeline must never wait on a slow browser."""

    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue[str]]] = defaultdict(set)

    def publish(self, crew_id: int, message: dict[str, Any]) -> None:
        subs = self._subs.get(crew_id)
        if not subs:
            return
        text = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        for q in subs:
            if q.full():
                continue
            q.put_nowait(text)

    def subscribe(self, crew_id: int) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX)
        self._subs[crew_id].add(q)
        return q

    def unsubscribe(self, crew_id: int, q: asyncio.Queue[str]) -> None:
        self._subs[crew_id].discard(q)


ensure_isimplementation(LiveHub, LiveBroadcasterProto)
