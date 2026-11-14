from datetime import UTC, date, datetime
from statistics import median

from src.app.application.monitoring.ports.repositories import (
    AggMinuteRepositoryProto,
    AlertRepositoryProto,
    MaintenanceRepositoryProto,
)
from src.app.application.monitoring.ports.services import (
    CheckinReaderProto,
    PersistenceQueueProto,
    RadiationSummaryProto,
    ReportStatusProto,
)
from src.app.application.monitoring.services.monitoring_engine import MonitoringEngine
from src.app.application.monitoring.services.presenters import (
    CABIN,
    VITALS,
    band,
    baseline_dto,
    card_state,
    chart_limits,
    current_minute,
    notice_dto,
    signal_of,
    vital_card,
)
from src.app.application.monitoring.services.sleep_service import SleepService
from src.app.domain.monitoring.constants.thresholds import CTX_NAMES, CTX_OFF, UNITS, rnd
from src.app.domain.monitoring.services.aggregation import minute_of
from src.app.shared_kernel.ports.result import Result, ResultDetailed, not_found
from src.vigil_types.monitoring.dto import (
    CoverageDTO,
    CrewRowDTO,
    DeviceBriefDTO,
    DeviceDTO,
    HealthDTO,
    LastNightDTO,
    MetricEventDTO,
    MetricNowDTO,
    MetricSeriesDTO,
    NightDTO,
    NoticeDTO,
    RecordDTO,
    SensorDTO,
    SleepDTO,
    TodayDTO,
)
from src.vigil_types.monitoring.queries import (
    AlertListQuery,
    CrewListQuery,
    CrewTodayQuery,
    DeviceStatusQuery,
    HealthQuery,
    MetricSeriesQuery,
    SleepQuery,
)

DAY = 86400
RANGE_S = {"1h": 3600, "24h": 86400, "7d": 7 * 86400}
# HARDCODED: the crew schedule is not in the schema yet; the design shows these
SLEEP_SCHEDULE = {"start": "21:30", "end": "06:00"}
SENSORS: list[tuple[str | None, list[str]]] = [
    ("optical", ["hr", "spo2"]),
    ("skin_temp", ["skin_t"]),
    (None, ["rr"]),   # derived, no sensor of its own
    (None, ["hrv"]),
    ("co2", ["ppco2"]),
    ("pressure", ["press"]),
    ("ambient", ["amb_t"]),
]


def _day_start(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


class _Base:
    def __init__(self, engine: MonitoringEngine) -> None:
        self._engine = engine

    def _known(self, crew_id: int) -> bool:
        return crew_id in self._engine.aggregates


class CrewTodayQueryHandler(_Base):
    def __init__(
        self,
        engine: MonitoringEngine,
        sleep: SleepService,
        checkins: CheckinReaderProto,
        reports: ReportStatusProto,
        radiation: RadiationSummaryProto,
        mission_start: date | None,
    ) -> None:
        super().__init__(engine)
        self._sleep, self._checkins, self._reports, self._radiation = sleep, checkins, reports, radiation
        self._mission_start = mission_start

    async def __call__(self, message: CrewTodayQuery) -> ResultDetailed[TodayDTO]:
        cid = message.crew_id
        if not self._known(cid):
            return not_found("Crew member not found", field="crew_id")
        e = self._engine
        agg, dev, now = e.aggregates[cid], e.device_of(cid), e.now_ts(cid)
        link = e.link(cid)
        cur = current_minute(agg, now, link)
        today = e.today(cid)
        frame = dev.last_frame if dev else None

        record: dict = {"checkin": {"filed_ts": None}, "sleep": None, "radiation": None, "report": {"queued_ts": None}}
        if today is not None:
            chk = await self._checkins.get(cid, today)
            record["checkin"] = {"filed_ts": chk.filed_ts if chk else None}
            ns = await self._sleep.last_nights(cid, today)
            record["sleep"] = {"minutes": ns[-1].minutes, "usual_minutes": SleepService.usual_minutes(ns[:-1] or ns)}
            record["report"] = {"queued_ts": await self._reports.queued_ts(cid, today)}
        record["radiation"] = await self._radiation.last_24h()

        return Result.ok(TodayDTO(
            now_ts=now,
            flight_day=self._flight_day(today),
            level=agg.level,
            critical_acked=agg.critical_acked,
            ctx=CTX_NAMES[cur.ctx] if cur else None,  # type: ignore[arg-type]
            baseline=baseline_dto(agg),
            device=DeviceBriefDTO(
                link=link,  # type: ignore[arg-type]
                worn=frame.worn if frame else None,
                signal=signal_of(frame.sqi) if frame else None,  # type: ignore[arg-type]
                batt=frame.batt_pct if frame else None,
            ),
            vitals=[vital_card(m, agg, dev, cur) for m in VITALS],
            cabin=[vital_card(m, agg, dev, cur) for m in CABIN],
            record=RecordDTO(**record),
            notices=[notice_dto(a, now) for a in agg.open_alerts()],
        ))

    def _flight_day(self, today: date | None) -> int | None:
        if today is None:
            return None
        start = self._mission_start
        if start is None and self._engine.first_day is not None:
            start = datetime.fromtimestamp(self._engine.first_day * DAY, tz=UTC).date()
        return (today - start).days + 1 if start else None


class CrewListQueryHandler(_Base):
    def __init__(self, engine: MonitoringEngine, sleep: SleepService, checkins: CheckinReaderProto) -> None:
        super().__init__(engine)
        self._sleep, self._checkins = sleep, checkins

    async def __call__(self, message: CrewListQuery) -> list[CrewRowDTO]:
        e = self._engine
        gnow = e.global_now()
        today = datetime.fromtimestamp(gnow, tz=UTC).date() if gnow else None
        filed = {(c.crew_id, c.day): c.filed_ts for c in await self._checkins.list_since(today)} if today else {}
        out = []
        for cid, info in e.crew.items():
            agg = e.aggregates[cid]
            data_min = agg.data_min_by_day.get(gnow // DAY, 0) if gnow else 0
            has_today = data_min > 0
            elapsed = (gnow % DAY) // 60 + 1 if gnow else 0
            sleep_mean: int | None | str = None
            if not info.shares("sleep"):
                sleep_mean = "not_shared"
            elif today is not None:
                ns = [n.minutes for n in (await self._sleep.last_nights(cid, today, 7)) if n.minutes]
                sleep_mean = int(sum(ns) / len(ns)) if ns else None
            out.append(CrewRowDTO(
                id=cid, name=info.name, role=info.role,
                level=agg.level if has_today else None,
                topic=self._topic(agg),
                baseline=baseline_dto(agg),
                checkin_ts="not_shared" if not info.shares("checkin") else filed.get((cid, today)),
                sleep_7n_mean_min=sleep_mean,
                data_today_pct=min(100, round(100 * data_min / elapsed)) if has_today and elapsed else None,
            ))
        return out

    @staticmethod
    def _topic(agg) -> str | None:
        inc = agg.incident
        if inc is None or inc.primary is None:
            return None
        return {"ppco2": "co2", "press": "pressure"}.get(inc.primary, inc.primary)


class MetricSeriesQueryHandler(_Base):
    def __init__(self, engine: MonitoringEngine, agg_repo: AggMinuteRepositoryProto) -> None:
        super().__init__(engine)
        self._repo = agg_repo

    async def __call__(self, message: MetricSeriesQuery) -> ResultDetailed[MetricSeriesDTO]:
        cid, m = message.crew_id, message.m
        if not self._known(cid):
            return not_found("Crew member not found", field="crew_id")
        e = self._engine
        agg, dev, now = e.aggregates[cid], e.device_of(cid), e.now_ts(cid)
        cur = current_minute(agg, now, e.link(cid))
        step = 600 if message.range == "7d" else 60
        points: list[list] = []
        if now is not None:
            end = minute_of(now)
            start = end - RANGE_S[message.range] + 60
            rows = await self._repo.series(cid, m, start, end)
            points = self._fill(m, rows, start, end, step)
        state, value, _ = card_state(m, agg, dev, cur)
        usual = None if m in CABIN else band(cur, m)
        shown = rnd(m, value)
        diff = None
        if shown is not None and usual:
            diff = 0 if usual[0] <= shown <= usual[1] else rnd(m, shown - (usual[0] if shown < usual[0] else usual[1]))
        lo_ts = points[0][0] if points else 0
        events = [
            MetricEventDTO(id=a.id or 0, ts_start=a.ts_start, ts_end=a.ts_end, level=a.peak_level,
                           pattern=a.pattern, ack=a.ack_ts is not None)
            for a in agg.open_alerts() if a.is_incident and (a.ts_end or now or 0) >= lo_ts
        ]
        return Result.ok(MetricSeriesDTO(
            m=m, unit=UNITS[m], range=message.range, step_s=step, now_ts=now,
            now=MetricNowDTO(value=shown, usual=usual, diff=diff,
                             ctx=CTX_NAMES[cur.ctx] if cur else None,  # type: ignore[arg-type]
                             signal=signal_of(cur.v.sqi) if cur else None,  # type: ignore[arg-type]
                             state=state),  # type: ignore[arg-type]
            points=points, limits=chart_limits(m), events=events,
        ))

    @staticmethod
    def _fill(m: str, rows, start: int, end: int, step: int) -> list[list]:
        """Missing minutes become explicit nulls: the chart must show the gap (§11.3)."""
        by_ts = {r[0]: r for r in rows}
        out: list[list] = []
        if step == 60:
            for ts in range(start, end + 1, 60):
                r = by_ts.get(ts)
                out.append([ts, rnd(m, r[1]), rnd(m, r[2]), rnd(m, r[3]), r[4]] if r else [ts, None, None, None, CTX_OFF])
            return out
        bucket_start = start - start % step
        for b in range(bucket_start, end + 1, step):
            rs = [by_ts[t] for t in range(b, b + step, 60) if t in by_ts]
            vals = [r[1] for r in rs if r[1] is not None]
            los = [r[2] for r in rs if r[2] is not None]
            his = [r[3] for r in rs if r[3] is not None]
            out.append([
                b,
                rnd(m, median(vals)) if vals else None,
                rnd(m, median(los)) if los else None,
                rnd(m, median(his)) if his else None,
                rs[-1][4] if rs else CTX_OFF,
            ])
        return out


class AlertListQueryHandler(_Base):
    LIMIT = 200

    def __init__(self, engine: MonitoringEngine, alert_repo: AlertRepositoryProto, queue: PersistenceQueueProto) -> None:
        super().__init__(engine)
        self._repo, self._queue = alert_repo, queue

    async def __call__(self, message: AlertListQuery) -> ResultDetailed[list[NoticeDTO]]:
        cid = message.crew_id
        if not self._known(cid):
            return not_found("Crew member not found", field="crew_id")
        now = self._engine.now_ts(cid)
        if message.open_only:
            return Result.ok([notice_dto(a, now) for a in self._engine.aggregates[cid].open_alerts()])
        await self._queue.flush(2.0)
        since = (now or 0) - 14 * DAY
        items = [a for a in await self._repo.list_since(since) if a.crew_id == cid]
        items.sort(key=lambda a: a.ts_start, reverse=True)
        return Result.ok([notice_dto(a, now) for a in items[: self.LIMIT]])


class DeviceStatusQueryHandler(_Base):
    def __init__(self, engine: MonitoringEngine, agg_repo: AggMinuteRepositoryProto) -> None:
        super().__init__(engine)
        self._repo = agg_repo

    async def __call__(self, message: DeviceStatusQuery) -> ResultDetailed[DeviceDTO]:
        cid = message.crew_id
        if not self._known(cid):
            return not_found("Crew member not found", field="crew_id")
        e = self._engine
        dev, now = e.device_of(cid), e.now_ts(cid)
        f = dev.last_frame if dev else None
        age = dev.link_age_s() if dev else None
        channels = dev.channels if dev else set()
        sensors = []
        for key, measures in SENSORS:
            working = any(x in channels for x in measures)
            status = "working" if working else ("not_installed" if key else "not_measured")
            sensors.append(SensorDTO(key=key, measures=measures, status=status))  # type: ignore[arg-type]
        coverage = CoverageDTO(data_min=0, nodata_min=0, spans=[])
        if now is not None:
            day0 = now - now % DAY
            end = minute_of(now) + 60
            rows = await self._repo.ctx_rows(cid, day0, end)
            have = {ts for ts, ctx in rows if ctx != CTX_OFF}
            spans: list[list] = []
            for ts in range(day0, end, 60):
                ok = ts in have
                if spans and spans[-1][2] == ok:
                    spans[-1][1] = ts + 60
                else:
                    spans.append([ts, ts + 60, ok])
            total = (end - day0) // 60
            coverage = CoverageDTO(data_min=len(have), nodata_min=total - len(have), spans=spans)
        return Result.ok(DeviceDTO(
            link=e.link(cid),  # type: ignore[arg-type]
            last_frame_age_s=None if age is None else int(age),
            worn=f.worn if f else None,
            worn_since_ts=dev.worn_since_ts if dev else None,
            signal=signal_of(f.sqi) if f else None,  # type: ignore[arg-type]
            sqi=f.sqi if f else None,
            batt=f.batt_pct if f else None,
            lost_pct_1h=dev.lost_pct_1h() if dev else None,
            sensors=sensors,
            coverage=coverage,
        ))


class SleepQueryHandler(_Base):
    def __init__(self, engine: MonitoringEngine, sleep: SleepService) -> None:
        super().__init__(engine)
        self._sleep = sleep

    async def __call__(self, message: SleepQuery) -> ResultDetailed[SleepDTO]:
        cid = message.crew_id
        if not self._known(cid):
            return not_found("Crew member not found", field="crew_id")
        today = self._engine.today(cid)
        if today is None:
            return Result.ok(SleepDTO(schedule=SLEEP_SCHEDULE, last_night=LastNightDTO(onset_ts=None, wake_ts=None, minutes=None),
                                      nights=[], usual_minutes=None))
        ns = await self._sleep.last_nights(cid, today)
        last = ns[-1]
        return Result.ok(SleepDTO(
            schedule=SLEEP_SCHEDULE,
            last_night=LastNightDTO(onset_ts=last.onset_ts, wake_ts=last.wake_ts, minutes=last.minutes),
            nights=[NightDTO(day=n.day.isoformat(), minutes=n.minutes) for n in ns],
            usual_minutes=SleepService.usual_minutes(ns[:-1] or ns),
        ))


class HealthQueryHandler(_Base):
    def __init__(self, engine: MonitoringEngine, maintenance: MaintenanceRepositoryProto, llm_enabled: bool) -> None:
        super().__init__(engine)
        self._maintenance, self._llm = maintenance, llm_enabled

    async def __call__(self, message: HealthQuery) -> HealthDTO:
        db = await self._maintenance.ping()
        return HealthDTO(ok=True, db=db, bad_frames=self._engine.bad_frames,
                         pattern_model=self._engine.classifier is not None, llm=self._llm)
