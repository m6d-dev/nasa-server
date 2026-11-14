"""Response shapes of BACKEND_TZ §11. `None` always means "no data"."""

from typing import Literal

from src.vigil_types.base import DTO, CtxName

Num = float | int
Band = list[Num] | None  # [lo, hi]

VitalState = Literal[
    "usual", "watch", "alert", "critical", "learning", "exercising", "no_data", "not_measured"
]
Trend = Literal["rising", "falling", "stable"]


class BaselineDTO(DTO):
    state: Literal["learning", "learned"]
    day: int
    of: int = 7
    ready_pct: int | None = None


class DeviceBriefDTO(DTO):
    link: Literal["connected", "no_link"]
    worn: bool | None
    signal: Literal["good", "fair", "poor"] | None
    batt: int | None


class VitalCardDTO(DTO):
    m: str
    value: Num | None
    unit: str
    state: VitalState
    learning: bool = False
    usual: Band = None
    limit: Num | None = None
    spark: list[Num | None]
    band: Band = None
    since_ts: int | None = None


class AlertTextDTO(DTO):
    what: str
    why: str
    action: list[str]


class AlertMetricDTO(DTO):
    m: str
    value: Num | None
    usual: Band
    z: float | None
    trend: Trend
    since_min: int
    slope_per_min: float | None = None


class NoticeDTO(DTO):
    id: int
    crew: int
    key: str
    source: str
    level: int
    peak_level: int
    ts_start: int
    ts_end: int | None
    since_min: int
    pattern: str | None
    p: float | None
    ctx: CtxName | None
    primary: str | None
    metrics: list[AlertMetricDTO]
    text: AlertTextDTO | None
    text_src: Literal["template", "llm"] | None
    ack_ts: int | None


class RecordDTO(DTO):
    checkin: dict
    sleep: dict | str
    radiation: dict | None
    report: dict


class TodayDTO(DTO):
    now_ts: int | None
    flight_day: int | None
    level: int
    critical_acked: bool
    ctx: CtxName | None
    baseline: BaselineDTO
    device: DeviceBriefDTO
    vitals: list[VitalCardDTO]
    cabin: list[VitalCardDTO]
    record: RecordDTO
    notices: list[NoticeDTO]


class MetricNowDTO(DTO):
    value: Num | None
    usual: Band
    diff: Num | None
    ctx: CtxName | None
    signal: Literal["good", "fair", "poor"] | None
    state: VitalState


class MetricLimitDTO(DTO):
    value: Num
    kind: Literal["watch_above", "alert_above", "alert_below", "critical_above", "critical_below"]


class MetricEventDTO(DTO):
    id: int
    ts_start: int
    ts_end: int | None
    level: int
    pattern: str | None
    ack: bool


class MetricSeriesDTO(DTO):
    m: str
    unit: str
    range: str
    step_s: int
    now_ts: int | None
    now: MetricNowDTO
    points: list[list[Num | None]]  # [ts, value, lo, hi, ctx]
    limits: list[MetricLimitDTO]
    events: list[MetricEventDTO]


class CrewRowDTO(DTO):
    id: int
    name: str
    role: str
    level: int | None
    topic: str | None
    baseline: BaselineDTO
    checkin_ts: int | None | Literal["not_shared"]
    sleep_7n_mean_min: int | None | Literal["not_shared"]
    data_today_pct: int | None


class SensorDTO(DTO):
    key: str | None
    measures: list[str]
    status: Literal["working", "not_installed", "not_measured"]


class CoverageDTO(DTO):
    data_min: int
    nodata_min: int
    spans: list[list[int | bool]] | None = None  # [start, end, has_data]


class DeviceDTO(DTO):
    link: Literal["connected", "no_link"]
    last_frame_age_s: int | None
    worn: bool | None
    worn_since_ts: int | None
    signal: Literal["good", "fair", "poor"] | None
    sqi: int | None
    batt: int | None
    lost_pct_1h: float | None
    sensors: list[SensorDTO]
    coverage: CoverageDTO


class NightDTO(DTO):
    day: str
    minutes: int | None


class LastNightDTO(DTO):
    onset_ts: int | None
    wake_ts: int | None
    minutes: int | None


class SleepDTO(DTO):
    schedule: dict[str, str]
    last_night: LastNightDTO
    nights: list[NightDTO]
    usual_minutes: int | None


class HealthDTO(DTO):
    ok: bool
    db: bool
    bad_frames: int
    pattern_model: bool
    llm: bool
