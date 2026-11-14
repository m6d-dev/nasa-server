from datetime import date

from sqlalchemy import Date, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.app.data_access.orm.base.base_orm_models import DatabaseTable, SqlAlchemyBaseModel


class RadiationDailyOrmModel(SqlAlchemyBaseModel):
    __tablename__ = DatabaseTable.RADIATION_DAILY

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    dose: Mapped[float] = mapped_column(Float(precision=24), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    instrument: Mapped[str] = mapped_column(Text, nullable=False)
