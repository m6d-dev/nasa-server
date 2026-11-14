from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.data_access.orm.base.base_orm_models import DatabaseTable, SqlAlchemyBaseModel


class CrewOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.CREW

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    dev_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    share: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CheckinOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.CHECKIN

    crew_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    sleep_q: Mapped[int | None] = mapped_column(SmallInteger)
    mood: Mapped[int | None] = mapped_column(SmallInteger)
    energy: Mapped[int | None] = mapped_column(SmallInteger)
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    filed_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
