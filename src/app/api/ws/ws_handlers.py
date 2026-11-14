import asyncio
import contextlib
import logging
from typing import Annotated

from litestar import WebSocket, websocket
from litestar.exceptions import WebSocketDisconnect
from litestar.params import Parameter

from src.app.infra.impls.live_hub import LiveHub
from src.app.shared_kernel.ports.mediator import MediatorProto
from src.vigil_types.base import CREW_ID_MAX
from src.vigil_types.monitoring.commands import IngestFrameCommand

logger = logging.getLogger("vigil.ws")


@websocket("/ingest")
async def ingest(socket: WebSocket, mediator: MediatorProto) -> None:
    """Binary frames, one per message; one socket may carry several dev_ids (§3)."""
    await socket.accept()
    try:
        while True:
            data = await socket.receive_data(mode="binary")
            if isinstance(data, str):
                data = data.encode()
            await mediator.send(IngestFrameCommand(raw=data[:128]))
    except WebSocketDisconnect:
        pass


@websocket("/live")
async def live(
    socket: WebSocket,
    live_hub: LiveHub,
    crew: Annotated[int, Parameter(query="crew", ge=1, le=CREW_ID_MAX)] = 1,
) -> None:
    await socket.accept()
    q = live_hub.subscribe(crew)

    async def pump() -> None:
        while True:
            await socket.send_text(await q.get())

    sender = asyncio.create_task(pump())
    try:
        while True:  # the client says nothing; this only notices it leaving
            await socket.receive_data(mode="text")
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await sender
        live_hub.unsubscribe(crew, q)
