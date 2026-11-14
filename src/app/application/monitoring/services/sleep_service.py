from datetime import date, timedelta
from statistics import median

from src.app.application.monitoring.ports.repositories import AggMinuteRepositoryProto
from src.app.domain.monitoring.services.sleep import Night, night_window, nights

USUAL_NIGHTS = 14


class SleepService:
    """Nights are derived from agg_1m.ctx on demand — no table of their own."""

    def __init__(self, agg_repo: AggMinuteRepositoryProto) -> None:
        self._repo = agg_repo

    async def last_nights(self, crew_id: int, today: date, n: int = USUAL_NIGHTS) -> list[Night]:
        days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
        start, _ = night_window(days[0])
        _, end = night_window(days[-1])
        rows = await self._repo.ctx_rows(crew_id, start, end)
        return nights(days, rows)

    @staticmethod
    def usual_minutes(ns: list[Night]) -> int | None:
        mins = [x.minutes for x in ns if x.minutes]
        return int(median(mins)) if mins else None
