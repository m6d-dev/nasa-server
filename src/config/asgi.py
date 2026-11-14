import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from litestar import Litestar, Router
from litestar.config.cors import CORSConfig
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin

from src.app.api.deps.api_deps import get_live_hub, get_mediator
from src.app.api.http.middlewares.middlewares import db_scope_middleware, exception_handler
from src.app.api.http.routers.crew.checkin_api import CheckinController
from src.app.api.http.routers.monitoring.crew_api import (
    AlertController,
    CrewMonitoringController,
    HealthController,
)
from src.app.api.http.routers.radiation.radiation_api import RadiationController
from src.app.api.http.routers.reporting.report_api import ReportController
from src.app.api.http.routers.simulation.sim_api import SimController
from src.app.api.ws.ws_handlers import ingest, live
from src.bootstrap import Bootstrap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
Bootstrap.init()


@asynccontextmanager
async def lifespan(_: Litestar) -> AsyncIterator[None]:
    await Bootstrap.startup()
    try:
        yield
    finally:
        await Bootstrap.shutdown()


def create_app() -> Litestar:
    cfg = Bootstrap.container().config.settings()
    origins = [o.strip() for o in cfg.cors_origin.split(",") if o.strip()] or ["*"]
    root = Router(
        path="",
        route_handlers=[
            HealthController, CrewMonitoringController, AlertController, CheckinController,
            ReportController, RadiationController, SimController, ingest, live,
        ],
    )
    return Litestar(
        route_handlers=[root],
        lifespan=[lifespan],
        middleware=[db_scope_middleware],
        exception_handlers={Exception: exception_handler},
        cors_config=CORSConfig(allow_origins=origins, allow_methods=["*"], allow_headers=["*"]),
        dependencies={
            "mediator": Provide(get_mediator, sync_to_thread=False),
            "live_hub": Provide(get_live_hub, sync_to_thread=False),
        },
        openapi_config=OpenAPIConfig(
            title="Vigil API", version="1.0.0", path="/docs",
            render_plugins=[SwaggerRenderPlugin()],
        ),
        logging_config=None,
    )


app = create_app()
