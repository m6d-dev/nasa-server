import logging

from litestar import MediaType, Request, Response
from litestar.exceptions import HTTPException, ValidationException
from litestar.types import ASGIApp, Receive, Scope, Send
from pydantic import ValidationError

from src.app.data_access.orm.unit_of_work import db_scope
from src.app.shared_kernel.errors.app_exception import AppException
from src.bootstrap import Bootstrap

logger = logging.getLogger("vigil.api")


def db_scope_middleware(app: ASGIApp) -> ASGIApp:
    """One DB session per HTTP request. WebSockets get none: ingest never touches the DB."""

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        async with db_scope(Bootstrap.container().db.session_factory()):
            await app(scope, receive, send)

    return middleware


def exception_handler(_: Request, exc: Exception) -> Response:
    if isinstance(exc, AppException):
        return Response(exc.as_dict(), status_code=exc.http_status, media_type=MediaType.JSON)
    if isinstance(exc, ValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return Response({"message": "Invalid input", "status": "invalid", "details": details},
                        status_code=400, media_type=MediaType.JSON)
    if isinstance(exc, ValidationException):
        return Response({"message": "Invalid input", "status": "invalid", "details": exc.extra},
                        status_code=400, media_type=MediaType.JSON)
    if isinstance(exc, HTTPException):
        if exc.status_code >= 500:
            logger.error("server error: %s", exc.detail, exc_info=exc.__cause__ or exc)
        return Response({"message": exc.detail}, status_code=exc.status_code, media_type=MediaType.JSON)
    logger.exception("unhandled error")
    return Response({"message": "Internal server error"}, status_code=500, media_type=MediaType.JSON)
