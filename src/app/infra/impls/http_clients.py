import logging
from typing import Any

import httpx

from src.app.application.narration.ports.services import LlmClientProto
from src.app.application.simulation.ports.services import VdevClientProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

logger = logging.getLogger("vigil.http")


class OllamaClient(LlmClientProto):
    TEMPERATURE = 0.2
    MAX_TOKENS = 160

    def __init__(self, base_url: str, model: str, timeout_s: float) -> None:
        self._url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._client = httpx.AsyncClient(timeout=timeout_s) if self._url else None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def generate(self, prompt: str) -> str | None:
        if self._client is None:
            return None
        try:
            r = await self._client.post(f"{self._url}/api/generate", json={
                "model": self._model, "prompt": prompt, "stream": False,
                "options": {"temperature": self.TEMPERATURE, "num_predict": self.MAX_TOKENS},
            })
            r.raise_for_status()
            return str(r.json().get("response") or "")
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("ollama unavailable: %s", exc)
            return None

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()


class VdevClient(VdevClientProto):
    TIMEOUT_S = 5.0

    def __init__(self, base_url: str) -> None:
        self._url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=self.TIMEOUT_S)

    async def request(self, method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any] | None:
        try:
            r = await self._client.request(method, f"{self._url}{path}", json=body)
        except httpx.HTTPError as exc:
            logger.info("vdev unavailable: %s", exc)
            return None
        try:
            payload: Any = r.json()
        except ValueError:
            payload = r.text[:2000] or None
        return r.status_code, payload

    async def aclose(self) -> None:
        await self._client.aclose()


ensure_isimplementation(OllamaClient, LlmClientProto)
ensure_isimplementation(VdevClient, VdevClientProto)
