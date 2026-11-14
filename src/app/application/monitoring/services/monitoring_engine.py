"""In-memory monitoring state for the whole crew (BACKEND_TZ §1: one process,
state in memory). Frames in → aggregates step → events out to the bus.

Everything here is synchronous: a frame is fully processed before the next one
is read, so ordering per device is guaranteed without locks.
"""

import logging
from datetime import UTC, date, datetime
from itertools import count

from src.app.application.crew.ports.repositories import CrewInfo
from src.app.application.monitoring.ports.services import LiveBroadcasterProto
from src.app.application.monitoring.services.device_registry import DeviceState
from src.app.domain.monitoring.aggregates.crew_monitor import CrewMonitorAggregate, day_str
from src.app.domain.monitoring.constants.thresholds import CTX_NAMES, rnd
from src.app.domain.monitoring.entities.alert import AlertEntity
from src.app.domain.monitoring.entities.minute import MinuteValues, ppco2_mmhg
from src.app.domain.monitoring.events.monitoring_events import AlertChanged
from src.app.domain.monitoring.ports.pattern_classifier import PatternClassifierProto
from src.app.domain.monitoring.services.aggregation import (
    MinuteAccumulator,
    from_minute_frame,
)
from src.app.domain.narration.entities.narration import ActionLibrary
from src.app.shared_kernel.ports.event import EventBusProto
from src.vigil_types.ingest.frame import TYPE_MINUTE, Frame, FrameReject, decode

logger = logging.getLogger("vigil.engine")
DAY = 86400


class MonitoringEngine:
    def __init__(
        self,
        bus: EventBusProto,
        live: LiveBroadcasterProto,
        classifier: PatternClassifierProto | None,
        actions: ActionLibrary,
        link_timeout_s: float,
    ) -> None:
        self._bus = bus
        self._live = live
        self.classifier = classifier
        self.actions = actions
        self.link_timeout_s = link_timeout_s
        self.crew: dict[int, CrewInfo] = {}
        self.aggregates: dict[int, CrewMonitorAggregate] = {}
        self.devices: dict[int, DeviceState] = {}  # by dev_id
        self._acc: dict[int, MinuteAccumulator] = {}
        self._ids = count(1)
        self.bad_frames = 0
        self.rejected = {r.name.lower(): 0 for r in FrameReject} | {"unknown_dev": 0, "stale": 0}
        self.filed_checkins: set[tuple[int, str]] = set()
        self._checkin_day: dict[int, str] = {}
        self.first_day: int | None = None

    # --- setup ---

    def configure(self, crew: list[CrewInfo], max_alert_id: int) -> None:
        self.crew = {c.id: c for c in crew}
        self.aggregates = {c.id: CrewMonitorAggregate(c.id) for c in crew}
        self.devices = {c.dev_id: DeviceState(c.dev_id, c.id) for c in crew}
        self._acc = {c.dev_id: MinuteAccumulator(c.id) for c in crew}
        self._ids = count(max_alert_id + 1)

    def restore(self, crew_id: int, rows: list[dict], open_alerts: list[AlertEntity]) -> None:
        agg = self.aggregates[crew_id]
        agg.restore(rows, open_alerts)
        if rows:
            last_ts = int(rows[-1]["ts"].timestamp())
            dev = self.device_of(crew_id)
            if dev is not None:
                # anything up to the end of the last stored minute was already accepted
                dev.last_ts = last_ts + 59
                dev.channels |= agg.channels
            first = int(rows[0]["ts"].timestamp()) // DAY
            self.first_day = first if self.first_day is None else min(self.first_day, first)

    def reset(self) -> None:
        for agg in self.aggregates.values():
            agg.reset()
        for dev_id, dev in list(self.devices.items()):
            self.devices[dev_id] = DeviceState(dev_id, dev.crew_id)
        for acc in self._acc.values():
            acc.drop()
        self.filed_checkins.clear()
        self._checkin_day.clear()
        self.first_day = None
        self.bad_frames = 0
        self.rejected = {k: 0 for k in self.rejected}

    # --- frames ---

    def accept(self, raw: bytes) -> None:
        f = decode(raw)
        if isinstance(f, FrameReject):
            self.bad_frames += 1
            self.rejected[f.name.lower()] += 1
            return
        dev = self.devices.get(f.dev_id)
        if dev is None:
            self.rejected["unknown_dev"] += 1
            return
        if not dev.accept(f):
            self.rejected["stale"] += 1
            return
        if not f.history:
            self._tick(dev.crew_id, f)
        if f.type == TYPE_MINUTE:
            self._acc[f.dev_id].drop()
            self._step(dev.crew_id, from_minute_frame(dev.crew_id, f))
        else:
            closed = self._acc[f.dev_id].add(f)
            if closed is not None:
                self._step(dev.crew_id, closed)

    def _tick(self, crew_id: int, f: Frame) -> None:
        agg = self.aggregates[crew_id]
        last = agg.last
        self._live.publish(crew_id, {
            "t": "tick", "ts": f.ts,
            "ctx": CTX_NAMES[last.ctx] if last else None,
            "level": agg.level,
            "v": {
                "hr": rnd("hr", f.hr), "spo2": rnd("spo2", f.spo2), "rr": rnd("rr", f.rr),
                "skin_t": rnd("skin_t", f.skin_t),
                "ppco2": rnd("ppco2", ppco2_mmhg(f.co2_ppm, f.press_hpa)),
                "press": rnd("press", f.press_hpa), "amb_t": rnd("amb_t", f.amb_t),
            },
            "sqi": f.sqi, "worn": f.worn,
        })

    def _step(self, crew_id: int, v: MinuteValues) -> None:
        agg = self.aggregates[crew_id]
        agg.on_minute(v, self.classifier, self.actions)
        day = v.ts // DAY
        if self.first_day is None:
            self.first_day = day
        if not v.history and self._checkin_day.get(crew_id) != day_str(day):
            d = day_str(day)
            self._checkin_day[crew_id] = d
            agg.ensure_checkin_notice(d, (crew_id, d) in self.filed_checkins, v.ts)
        self._dispatch(agg)

    def _dispatch(self, agg: CrewMonitorAggregate) -> None:
        events = agg.pull_events()
        for e in events:
            if isinstance(e, AlertChanged) and e.alert.id is None:
                e.alert.id = next(self._ids)  # ids are ours; the writer upserts by id
        self._bus.publish_many(events)

    # --- commands from the API ---

    def ack(self, alert_id: int) -> AlertEntity | None:
        for crew_id, agg in self.aggregates.items():
            a = agg.ack(alert_id, self.now_ts(crew_id) or 0)
            if a is not None:
                self._dispatch(agg)
                return a
        return None

    def apply_llm_text(self, crew_id: int, alert_id: int, text_rev: int, text: dict) -> bool:
        agg = self.aggregates.get(crew_id)
        if agg is None or not agg.set_llm_text(alert_id, text_rev, text):
            return False
        self._dispatch(agg)
        return True

    def note_checkin(self, crew_id: int, day: date, symptoms: tuple[str, ...]) -> None:
        d = day.isoformat()
        self.filed_checkins.add((crew_id, d))
        agg = self.aggregates[crew_id]
        if d == self.today_str(crew_id):
            agg.symptoms = symptoms  # goes into the LLM summary (§9)
        if self._checkin_day.get(crew_id) == d:
            agg.ensure_checkin_notice(d, True, self.now_ts(crew_id) or 0)  # closes the To do
        self._dispatch(agg)

    # --- reads ---

    def has_crew(self, crew_id: int) -> bool:
        return crew_id in self.aggregates

    def device_of(self, crew_id: int) -> DeviceState | None:
        info = self.crew.get(crew_id)
        return self.devices.get(info.dev_id) if info else None

    def now_ts(self, crew_id: int) -> int | None:
        """Virtual "now" of a person: ts of the last frame (§4)."""
        dev = self.device_of(crew_id)
        return dev.last_ts if dev else None

    def global_now(self) -> int | None:
        stamps = [d.last_ts for d in self.devices.values() if d.last_ts is not None]
        return max(stamps) if stamps else None

    def today(self, crew_id: int) -> date | None:
        now = self.now_ts(crew_id)
        return None if now is None else datetime.fromtimestamp(now, tz=UTC).date()

    def today_str(self, crew_id: int) -> str | None:
        d = self.today(crew_id)
        return d.isoformat() if d else None

    def link(self, crew_id: int) -> str:
        dev = self.device_of(crew_id)
        age = dev.link_age_s() if dev else None
        return "connected" if age is not None and age <= self.link_timeout_s else "no_link"

    def find_alert(self, alert_id: int) -> AlertEntity | None:
        for agg in self.aggregates.values():
            for a in agg.open_alerts():
                if a.id == alert_id:
                    return a
        return None
