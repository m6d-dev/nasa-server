from typing import Any, Protocol


class VdevClientProto(Protocol):
    """HTTP to the virtual device. `None` means vdev is unreachable (→ 503)."""

    async def request(self, method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any] | None: ...


class RuntimeResetProto(Protocol):
    """Clears agg_1m, alert, checkin, report and all in-memory state (§11.10)."""

    async def reset_all(self) -> None: ...
