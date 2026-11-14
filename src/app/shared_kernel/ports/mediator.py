from typing import Any, Protocol, runtime_checkable

from src.app.shared_kernel.types.cqrs import CQHandlerFactory, CQHandlerPolicy
from src.vigil_types import Command, Query


@runtime_checkable  # Litestar isinstance-checks injected dependencies
class MediatorProto(Protocol):
    def register_command(
        self,
        command: type[Command],
        handler_factory: CQHandlerFactory[Any, Any],
        policy: CQHandlerPolicy,
    ) -> None: ...

    def register_query(
        self,
        query: type[Query],
        handler_factory: CQHandlerFactory[Any, Any],
        policy: CQHandlerPolicy,
    ) -> None: ...

    async def send(self, cmd: Command) -> Any: ...

    async def ask(self, query: Query) -> Any: ...
