import inspect
from typing import Any

from src.app.shared_kernel.ports.mediator import MediatorProto
from src.app.shared_kernel.types.cqrs import CQHandlerFactory, CQHandlerPolicy
from src.app.shared_kernel.utils.assertion import ensure_isimplementation
from src.vigil_types import Command, Query


class Mediator(MediatorProto):
    """Registry + policy check, as in the CRM, minus RBAC and redaction.

    `policy` is required on registration, so there is no unguarded message;
    today every policy is public (no user auth, BACKEND_TZ §17).
    """

    def __init__(self) -> None:
        self._commands: dict[type[Command], CQHandlerFactory[Any, Any]] = {}
        self._queries: dict[type[Query], CQHandlerFactory[Any, Any]] = {}
        self._policies: dict[type, CQHandlerPolicy] = {}

    def register_command(self, command: type[Command], handler_factory: CQHandlerFactory[Any, Any],
                         policy: CQHandlerPolicy) -> None:
        self._commands[command] = handler_factory
        self._policies[command] = policy

    def register_query(self, query: type[Query], handler_factory: CQHandlerFactory[Any, Any],
                       policy: CQHandlerPolicy) -> None:
        self._queries[query] = handler_factory
        self._policies[query] = policy

    async def send(self, cmd: Command) -> Any:
        return await self._invoke(self._commands, cmd)

    async def ask(self, query: Query) -> Any:
        return await self._invoke(self._queries, query)

    async def _invoke(self, table: dict, message: Any) -> Any:
        factory = table.get(type(message))
        if factory is None:
            raise LookupError(f"No handler registered for {type(message).__name__}")
        if not self._policies[type(message)].public:
            raise PermissionError(type(message).__name__)  # no non-public policy exists yet
        result = factory()(message)
        return await result if inspect.isawaitable(result) else result


ensure_isimplementation(Mediator, MediatorProto)
