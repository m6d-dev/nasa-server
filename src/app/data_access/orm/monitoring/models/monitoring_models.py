from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.data_access.orm.base.base_orm_models import DatabaseTable, SqlAlchemyBaseModel

Real = Float(precision=24)  # postgres `real`

AGG_COLUMNS = (
    "crew_id", "ts", "hr", "spo2", "rr", "skin_t", "hrv", "co2_ppm", "press_hpa", "amb_t",
    "ppco2", "act_mg", "sqi", "worn_frac", "valid_s", "ctx",
    "z_hr", "z_spo2", "z_rr", "z_skin_t",
    "lo_hr", "hi_hr", "lo_spo2", "hi_spo2", "lo_rr", "hi_rr", "lo_skin_t", "hi_skin_t",
    "level", "learn_mask",
)


class AggMinuteOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.AGG_1M

    crew_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hr: Mapped[float | None] = mapped_column(Real)
    spo2: Mapped[float | None] = mapped_column(Real)
    rr: Mapped[float | None] = mapped_column(Real)
    skin_t: Mapped[float | None] = mapped_column(Real)
    hrv: Mapped[float | None] = mapped_column(Real)
    co2_ppm: Mapped[float | None] = mapped_column(Real)
    press_hpa: Mapped[float | None] = mapped_column(Real)
    amb_t: Mapped[float | None] = mapped_column(Real)
    ppco2: Mapped[float | None] = mapped_column(Real)
    act_mg: Mapped[float | None] = mapped_column(Real)
    sqi: Mapped[float | None] = mapped_column(Real)
    worn_frac: Mapped[float | None] = mapped_column(Real)
    valid_s: Mapped[int | None] = mapped_column(SmallInteger)
    ctx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    z_hr: Mapped[float | None] = mapped_column(Real)
    z_spo2: Mapped[float | None] = mapped_column(Real)
    z_rr: Mapped[float | None] = mapped_column(Real)
    z_skin_t: Mapped[float | None] = mapped_column(Real)
    lo_hr: Mapped[float | None] = mapped_column(Real)
    hi_hr: Mapped[float | None] = mapped_column(Real)
    lo_spo2: Mapped[float | None] = mapped_column(Real)
    hi_spo2: Mapped[float | None] = mapped_column(Real)
    lo_rr: Mapped[float | None] = mapped_column(Real)
    hi_rr: Mapped[float | None] = mapped_column(Real)
    lo_skin_t: Mapped[float | None] = mapped_column(Real)
    hi_skin_t: Mapped[float | None] = mapped_column(Real)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    learn_mask: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class AlertOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.ALERT

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    crew_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    ts_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ts_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ts_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    peak_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pattern: Mapped[str | None] = mapped_column(Text)
    p: Mapped[float | None] = mapped_column(Real)
    ctx: Mapped[int | None] = mapped_column(SmallInteger)
    primary_m: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    text: Mapped[dict | None] = mapped_column(JSONB)
    text_src: Mapped[str | None] = mapped_column(Text)
    ack_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
