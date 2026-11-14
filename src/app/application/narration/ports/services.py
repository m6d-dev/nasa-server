from typing import Protocol


class LlmClientProto(Protocol):
    """Local LLM (Ollama, model `vigil-narrator`). `None` on timeout or error."""

    @property
    def enabled(self) -> bool: ...

    async def generate(self, prompt: str) -> str | None: ...


class AlertTextSinkProto(Protocol):
    """Where an accepted LLM text goes. Bound to the monitoring engine."""

    def apply_llm_text(self, crew_id: int, alert_id: int, text_rev: int, text: dict) -> bool: ...
