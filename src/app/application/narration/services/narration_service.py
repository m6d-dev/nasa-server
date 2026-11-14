"""LLM text in the background (BACKEND_TZ §9, step 2). The template is already
on screen; this only ever replaces it with something checked."""

import asyncio
import json
import logging

from src.app.application.narration.ports.services import AlertTextSinkProto, LlmClientProto
from src.app.domain.monitoring.events.monitoring_events import NarrationRequested
from src.app.domain.narration.validation.llm_reply import parse_reply
from src.app.shared_kernel.ports.event import TaskSpawnerProto

logger = logging.getLogger("vigil.narrator")


class NarrationService:
    def __init__(self, llm: LlmClientProto, sink: AlertTextSinkProto, tasks: TaskSpawnerProto) -> None:
        self._llm, self._sink, self._tasks = llm, sink, tasks
        self._one_at_a_time = asyncio.Lock()

    def request(self, event: NarrationRequested) -> None:
        if self._llm.enabled:
            self._tasks.spawn(self._narrate(event), name=f"narrate-{event.alert.id}")

    async def _narrate(self, event: NarrationRequested) -> None:
        summary = event.summary.as_llm_json()
        async with self._one_at_a_time:
            if event.alert.text_rev != event.text_rev or not event.alert.is_open:
                return  # superseded while waiting
            reply = await self._llm.generate(json.dumps(summary, ensure_ascii=False))
        if reply is None:
            logger.info("llm: no answer for alert %s, template stays", event.alert.id)
            return
        text = parse_reply(reply, summary)
        if text is None:
            logger.info("llm: rejected answer for alert %s, template stays", event.alert.id)
            return
        self._sink.apply_llm_text(event.crew_id, event.alert.id or 0, event.text_rev, text.as_dict())
