from src.vigil_types.base import ATCrewId, MetricCode, Query, RangeCode


class CrewListQuery(Query): ...


class CrewTodayQuery(Query):
    crew_id: ATCrewId


class MetricSeriesQuery(Query):
    crew_id: ATCrewId
    m: MetricCode
    range: RangeCode = "1h"


class AlertListQuery(Query):
    crew_id: ATCrewId
    open_only: bool = False


class DeviceStatusQuery(Query):
    crew_id: ATCrewId


class SleepQuery(Query):
    crew_id: ATCrewId


class HealthQuery(Query): ...
