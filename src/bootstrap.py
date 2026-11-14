"""Process wiring: DI, CQRS registration, event subscriptions, start-up restore."""

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.app.application.radiation.services.radlab_loader import load_radlab
from src.app.infra.cqrs.register_all import register_all
from src.app.infra.di.root_di import RootDIContainer, build
from src.app.infra.event_sourcing.subscribers import subscribe_all
from src.app.shared_kernel.ports.mediator import MediatorProto

logger = logging.getLogger("vigil.bootstrap")
SCHEMA_SQL = Path(__file__).parent / "app" / "data_access" / "sql" / "schema.sql"
RESTORE_DAYS = 14
DB_WAIT_S = 60


class Bootstrap:
    _container: RootDIContainer | None = None
    _mediator: MediatorProto | None = None

    @classmethod
    def init(cls) -> None:
        if cls._container is not None:
            return
        cls._container = build()
        cls._mediator = register_all(cls._container)
        subscribe_all(cls._container)

    @classmethod
    def container(cls) -> RootDIContainer:
        assert cls._container is not None, "Bootstrap.init() was not called"
        return cls._container

    @classmethod
    def mediator(cls) -> MediatorProto:
        assert cls._mediator is not None, "Bootstrap.init() was not called"
        return cls._mediator

    @classmethod
    async def startup(cls) -> None:
        c = cls.container()
        await cls._wait_for_db()
        scope = c.db.scope()
        async with scope():
            async with c.db.uow():
                if await c.monitoring.maintenance_repo().ensure_schema(SCHEMA_SQL.read_text()):
                    logger.info("schema created")
        await cls._restore()
        await cls._load_radiation()
        c.monitoring.queue().start()

    @classmethod
    async def _wait_for_db(cls) -> None:
        c = cls.container()
        for attempt in range(DB_WAIT_S):
            async with c.db.scope()():
                if await c.monitoring.maintenance_repo().ping():
                    return
            if attempt == 0:
                logger.warning("waiting for postgres…")
            await asyncio.sleep(1)
        raise RuntimeError("postgres is not reachable")

    @classmethod
    async def _restore(cls) -> None:
        """Norms from agg_1m, open incidents from alert (§6.6, §13)."""
        c = cls.container()
        engine = c.monitoring.engine()
        async with c.db.scope()():
            crew = await c.crew.crew_repo().list_all()
            alerts = c.monitoring.alert_repo()
            engine.configure(crew, await alerts.max_id())
            open_by_crew = defaultdict(list)
            for a in await alerts.list_open():
                open_by_crew[a.crew_id].append(a)
            agg = c.monitoring.agg_repo()
            last = await agg.last_ts_by_crew()
            for info in crew:
                end = last.get(info.id)
                rows = await agg.rows(info.id, end - RESTORE_DAYS * 86400, end + 60) if end else []
                engine.restore(info.id, rows, open_by_crew.get(info.id, []))
                if rows:
                    logger.info("restored crew %s: %d minutes, baseline %s", info.id, len(rows),
                                engine.aggregates[info.id].learn.state)
            since = datetime.now(UTC).date() - timedelta(days=3650)
            for chk in await c.crew.checkin_repo().list_since(since):
                engine.filed_checkins.add((chk.crew_id, chk.day.isoformat()))

    @classmethod
    async def _load_radiation(cls) -> None:
        c = cls.container()
        cfg = c.config.settings()
        days = load_radlab(cfg.radlab_dir, cfg.radlab_instrument, cfg.radlab_rate_unit)
        c.infra.radiation_summary().days = days
        async with c.db.scope()():
            async with c.db.uow():
                await c.radiation.radiation_repo().replace_all(days)
        logger.info("radiation: %d days from %s", len(days), cfg.radlab_dir)

    @classmethod
    async def shutdown(cls) -> None:
        c = cls.container()
        await c.monitoring.queue().stop()
        await c.infra.llm().aclose()
        await c.infra.vdev().aclose()
        await c.db.engine().dispose()
