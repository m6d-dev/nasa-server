from enum import StrEnum

from sqlalchemy.orm import DeclarativeBase


class SqlAlchemyBaseModel(DeclarativeBase):
    """Mirrors `data_access/sql/schema.sql`; never used to create tables."""


class DatabaseTable(StrEnum):
    CREW = "crew"
    AGG_1M = "agg_1m"
    ALERT = "alert"
    CHECKIN = "checkin"
    REPORT = "report"
    RADIATION_DAILY = "radiation_daily"
