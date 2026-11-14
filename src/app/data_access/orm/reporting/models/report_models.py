from datetime import date, datetime

from sqlalchemy import Date, DateTime, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.data_access.orm.base.base_orm_models import DatabaseTable, SqlAlchemyBaseModel


class ReportOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.REPORT

    crew_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    include: Mapped[dict] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    queued_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
