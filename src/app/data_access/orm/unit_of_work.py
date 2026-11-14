from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.shared_kernel.ports.db.unit_of_work import UnitOfWorkProto
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

# One session per scope: an HTTP request (middleware) or a background job.
# Repositories resolve it lazily, as in the CRM's db_session_registry.
_current_session: ContextVar[AsyncSession | None] = ContextVar("vigil_db_session", default=None)


def current_session() -> AsyncSession:
    s = _current_session.get()
    if s is None:
        raise RuntimeError("No DB scope: wrap the call in `db_scope()`")
    return s


@asynccontextmanager
async def db_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    session = factory()
    token = _current_session.set(session)
    try:
        yield session
    finally:
        _current_session.reset(token)
        await session.close()


class OrmUnitOfWork(UnitOfWorkProto):
    """Commits on clean exit, so validate before entering (CRM orm.md)."""

    __slots__ = ("db",)

    def __init__(self, session: AsyncSession) -> None:
        self.db = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val:
            await self.db.rollback()
        else:
            await self.db.commit()

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def flush(self) -> None:
        await self.db.flush()


ensure_isimplementation(OrmUnitOfWork, UnitOfWorkProto)
