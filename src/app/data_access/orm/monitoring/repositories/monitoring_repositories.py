import logging
from datetime import UTC, datetime
from typing import Any

import asyncpg
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.application.monitoring.ports.repositories import (
    AggMinuteRepositoryProto,
    AlertRepositoryProto,
    MaintenanceRepositoryProto,
    SeriesPoint,
)
from src.app.data_access.orm.base.base_orm_models import DatabaseTable
from src.app.data_access.orm.monitoring.models.monitoring_models import (
    AGG_COLUMNS,
    AggMinuteOrmModel,
    AlertOrmModel,
)
from src.app.domain.monitoring.entities.alert import AlertEntity
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

logger = logging.getLogger("vigil.db")

# metric code -> (value column, lo column, hi column)
SERIES_COLUMNS: dict[str, tuple[str, str | None, str | None]] = {
    "hr": ("hr", "lo_hr", "hi_hr"),
    "spo2": ("spo2", "lo_spo2", "hi_spo2"),
    "rr": ("rr", "lo_rr", "hi_rr"),
    "skin_t": ("skin_t", "lo_skin_t", "hi_skin_t"),
    "ppco2": ("ppco2", None, None),
    "press": ("press_hpa", None, None),
    "amb_t": ("amb_t", None, None),
}


def _dt(ts: int | None) -> datetime | None:
    return None if ts is None else datetime.fromtimestamp(ts, tz=UTC)


def _ts(dt: datetime | None) -> int | None:
    return None if dt is None else int(dt.timestamp())


class AggMinuteOrmRepository(AggMinuteRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def insert_many(self, rows: list[dict[str, Any]]) -> None:
        """COPY for speed during history replay (§10); upsert if a minute already exists.
        The caller's unit of work commits."""
        if not rows:
            return
        if len(rows) > 1:
            conn = await self._s.connection()
            raw = (await conn.get_raw_connection()).driver_connection
            try:
                async with raw.transaction():
                    await raw.copy_records_to_table(
                        DatabaseTable.AGG_1M.value,
                        records=[tuple(r[c] for c in AGG_COLUMNS) for r in rows],
                        columns=list(AGG_COLUMNS),
                    )
                return
            except asyncpg.UniqueViolationError:
                logger.info("agg_1m copy hit existing minutes; falling back to upsert")
        stmt = insert(AggMinuteOrmModel)
        stmt = stmt.on_conflict_do_update(
            index_elements=["crew_id", "ts"],
            set_={c: stmt.excluded[c] for c in AGG_COLUMNS if c not in ("crew_id", "ts")},
        )
        await self._s.execute(stmt, rows)

    async def series(self, crew_id: int, m: str, start_ts: int, end_ts: int) -> list[SeriesPoint]:
        vcol, locol, hicol = SERIES_COLUMNS[m]
        t = AggMinuteOrmModel
        cols = [t.ts, getattr(t, vcol),
                getattr(t, locol) if locol else None, getattr(t, hicol) if hicol else None, t.ctx]
        q = (select(*[c for c in cols if c is not None])
             .where(t.crew_id == crew_id, t.ts >= _dt(start_ts), t.ts <= _dt(end_ts))
             .order_by(t.ts))
        out: list[SeriesPoint] = []
        for row in (await self._s.execute(q)).all():
            if locol:
                ts, v, lo, hi, ctx = row
            else:
                ts, v, ctx = row
                lo = hi = None
            out.append((int(ts.timestamp()), v, lo, hi, ctx))
        return out

    async def ctx_rows(self, crew_id: int, start_ts: int, end_ts: int) -> list[tuple[int, int]]:
        t = AggMinuteOrmModel
        q = select(t.ts, t.ctx).where(t.crew_id == crew_id, t.ts >= _dt(start_ts), t.ts < _dt(end_ts)).order_by(t.ts)
        return [(int(ts.timestamp()), ctx) for ts, ctx in (await self._s.execute(q)).all()]

    async def rows(self, crew_id: int, start_ts: int, end_ts: int) -> list[dict[str, Any]]:
        t = AggMinuteOrmModel
        q = select(*[getattr(t, c) for c in AGG_COLUMNS]).where(
            t.crew_id == crew_id, t.ts >= _dt(start_ts), t.ts < _dt(end_ts)
        ).order_by(t.ts)
        return [dict(r._mapping) for r in (await self._s.execute(q)).all()]

    async def last_ts_by_crew(self) -> dict[int, int]:
        t = AggMinuteOrmModel
        q = select(t.crew_id, func.max(t.ts)).group_by(t.crew_id)
        return {cid: int(ts.timestamp()) for cid, ts in (await self._s.execute(q)).all()}


def _alert_to_row(a: AlertEntity) -> dict[str, Any]:
    return dict(
        id=a.id, crew_id=a.crew_id, key=a.key, source=a.source,
        ts_start=_dt(a.ts_start), ts_update=_dt(a.ts_update), ts_end=_dt(a.ts_end),
        level=a.level, peak_level=a.peak_level, pattern=a.pattern, p=a.p, ctx=a.ctx,
        primary_m=a.primary, metrics=a.metrics_json(), text=a.text, text_src=a.text_src,
        ack_ts=_dt(a.ack_ts),
    )


def _row_to_alert(r: AlertOrmModel) -> AlertEntity:
    return AlertEntity(
        id=r.id, crew_id=r.crew_id, key=r.key, source=r.source,
        ts_start=_ts(r.ts_start) or 0, ts_update=_ts(r.ts_update) or 0, ts_end=_ts(r.ts_end),
        level=r.level, peak_level=r.peak_level, pattern=r.pattern, p=r.p, ctx=r.ctx,
        primary=r.primary_m, metrics=AlertEntity.metrics_from_json(r.metrics or []),
        text=r.text, text_src=r.text_src, ack_ts=_ts(r.ack_ts),
    )


class AlertOrmRepository(AlertRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert_many(self, alerts: list[AlertEntity]) -> None:
        if not alerts:
            return
        rows = [_alert_to_row(a) for a in alerts]
        stmt = insert(AlertOrmModel)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"], set_={c: stmt.excluded[c] for c in rows[0] if c != "id"}
        )
        await self._s.execute(stmt, rows)

    async def list_since(self, since_ts: int) -> list[AlertEntity]:
        q = select(AlertOrmModel).where(AlertOrmModel.ts_start >= _dt(since_ts)).order_by(AlertOrmModel.id)
        return [_row_to_alert(r) for r in (await self._s.scalars(q)).all()]

    async def list_open(self) -> list[AlertEntity]:
        q = select(AlertOrmModel).where(AlertOrmModel.ts_end.is_(None)).order_by(AlertOrmModel.id)
        return [_row_to_alert(r) for r in (await self._s.scalars(q)).all()]

    async def max_id(self) -> int:
        return int((await self._s.scalar(select(func.coalesce(func.max(AlertOrmModel.id), 0)))) or 0)


class MaintenanceOrmRepository(MaintenanceRepositoryProto):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def ensure_schema(self, sql: str) -> bool:
        """Apply schema.sql if `crew` is missing. Returns True when it ran."""
        exists = await self._s.scalar(text("select to_regclass('public.crew') is not null"))
        if exists:
            return False
        conn = await self._s.connection()
        raw = (await conn.get_raw_connection()).driver_connection
        await raw.execute(sql)  # simple protocol: many statements at once
        return True

    async def truncate_runtime(self) -> None:
        await self._s.execute(text("truncate agg_1m, alert, checkin, report restart identity"))

    async def ping(self) -> bool:
        try:
            await self._s.execute(text("select 1"))
            return True
        except Exception:  # noqa: BLE001 - health must answer, not raise
            return False


ensure_isimplementation(AggMinuteOrmRepository, AggMinuteRepositoryProto)
ensure_isimplementation(AlertOrmRepository, AlertRepositoryProto)
ensure_isimplementation(MaintenanceOrmRepository, MaintenanceRepositoryProto)
