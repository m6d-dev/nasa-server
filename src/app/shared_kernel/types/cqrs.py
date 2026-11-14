from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src.vigil_types import Command, Query


@runtime_checkable
class CQHandler[CQ: Command | Query, R: Any](Protocol):
    def __call__(self, message: CQ) -> R | Awaitable[R]: ...


@runtime_checkable
class CQHandlerFactory[CQ: Command | Query, R: Any](Protocol):
    def __call__(self) -> CQHandler[CQ, R]: ...


@dataclass(frozen=True, slots=True)
class CQHandlerPolicy:
    """Who may send a message.

    Vigil has no user auth (BACKEND_TZ §2, §17), so every policy is public
    today. The argument stays required so the decision is visible at
    registration and a device-token policy (PR-2) has a place to go.
    """

    name: str
    public: bool = True


PUBLIC_POINT = CQHandlerPolicy(name="public")
# Ingest is reached by devices, not the dashboard. Same as public until PR-2.
DEVICE_POINT = CQHandlerPolicy(name="device")
