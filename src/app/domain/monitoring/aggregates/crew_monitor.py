"""One crew member's monitoring state and the per-minute step (BACKEND_TZ §5).

`on_minute` is the whole pipeline below minute closing. It does no I/O: it is
handed the classifier and the action library, and reports what happened as
events for the application layer to persist and broadcast. The same call is
what ML runs offline.
"""

from collections import deque
from datetime import UTC, datetime

from src.app.domain.monitoring.constants.thresholds import (
    BASELINE_METRICS,
    CRITICAL,
    CTX_NAMES,
    CTX_OFF,
    CTX_REST,
    HARD_LIMIT_QUOTE,
    LEARN_BIT,
    LEARN_MAX_ABS_Z,
    LEVEL_METRICS,
    PATTERN_P_WATCH,
    PATTERN_WATCH_MIN,
    PATTERN_WINDOW_MIN,
    PPCO2_ALERT,
    PPCO2_CRITICAL,
    PPCO2_WATCH,
    SLOPE_WINDOW_MIN,
    TREND_EPS,
    USUAL,
    WATCH,
    Z_WATCH,
    rnd,
)
from src.app.domain.monitoring.entities.alert import (
    CHECKIN_KEY_PREFIX,
    KEY_BASELINE_LEARNED,
    KEY_INCIDENT,
    AlertEntity,
    IncidentMetric,
)
from src.app.domain.monitoring.entities.minute import MetricEval, MinuteResult, MinuteValues
from src.app.domain.monitoring.events.monitoring_events import (
    AlertChanged,
    BaselineStateChanged,
    DayChanged,
    DomainEvent,
    LevelChanged,
    MinuteClosed,
    NarrationRequested,
)
from src.app.domain.monitoring.ports.pattern_classifier import PatternClassifierProto
from src.app.domain.monitoring.services.baseline import LearnState, PersonalBaseline
from src.app.domain.monitoring.services.context import ContextClassifier
from src.app.domain.monitoring.services.features import build_features
from src.app.domain.monitoring.services.levels import LevelDetector, z_counts
from src.app.domain.monitoring.services.pattern_rules import pattern_by_rule
from src.app.domain.monitoring.services.stats import slope_per_min
from src.app.domain.narration.entities.narration import (
    ActionLibrary,
    NarrationInput,
    NarrationMetric,
)
from src.app.domain.narration.services.template_narrator import compose

DAY = 86400
WINDOW_MIN = 60  # spark length; also covers the pattern and slope windows
_ENV_METRICS = ("ppco2", "press")
_CHANNELS = ("hr", "spo2", "rr", "skin_t", "hrv", "ppco2", "press", "amb_t")


def day_str(day_number: int) -> str:
    return datetime.fromtimestamp(day_number * DAY, tz=UTC).date().isoformat()


def _trend(m: str, slope: float | None) -> str:
    if slope is None or abs(slope) < TREND_EPS.get(m, 0.1):
        return "stable"
    return "rising" if slope > 0 else "falling"


def _ppco2_limit(level: int) -> float:
    return PPCO2_CRITICAL if level >= CRITICAL else PPCO2_ALERT if level > WATCH else PPCO2_WATCH


class CrewMonitorAggregate:
    def __init__(self, crew_id: int) -> None:
        self.crew_id = crew_id
        self.context = ContextClassifier()
        self.baseline = PersonalBaseline()
        self.detector = LevelDetector()
        self.window: deque[MinuteResult] = deque(maxlen=WINDOW_MIN)
        self.incident: AlertEntity | None = None
        self.notices: dict[str, AlertEntity] = {}  # open system notices by key
        self.learn = LearnState("learning", 0, 0)
        self.day: int | None = None
        self.channels: set[str] = set()  # metrics this device has ever sent
        self.data_min_by_day: dict[int, int] = {}
        self.symptoms: tuple[str, ...] = ()
        self._pattern_streak = 0
        self._events: list[DomainEvent] = []

    # --- read side ---

    @property
    def level(self) -> int:
        return self.detector.level

    @property
    def critical_acked(self) -> bool:
        inc = self.incident
        return bool(inc and inc.level >= CRITICAL and inc.ack_ts is not None)

    @property
    def last(self) -> MinuteResult | None:
        return self.window[-1] if self.window else None

    def open_alerts(self) -> list[AlertEntity]:
        items = list(self.notices.values())
        if self.incident:
            items.insert(0, self.incident)
        return items

    def pull_events(self) -> list[DomainEvent]:
        ev, self._events = self._events, []
        return ev

    # --- the step ---

    def on_minute(
        self,
        v: MinuteValues,
        classifier: PatternClassifierProto | None,
        actions: ActionLibrary,
    ) -> MinuteResult:
        day = v.ts // DAY
        if self.day is not None and day != self.day:
            self._events.append(DayChanged(self.crew_id, self.day, day, v.history))
            self.data_min_by_day = {d: n for d, n in self.data_min_by_day.items() if d > day - 15}
        self.day = day

        self.baseline.maybe_recalc(v.ts)
        ctx = self.context.classify(v, self.baseline.rest_hr_median())
        if ctx != CTX_OFF:
            self.baseline.note_day(v.ts)
            self.data_min_by_day[day] = self.data_min_by_day.get(day, 0) + 1
        for m in _CHANNELS:
            if m not in self.channels and v.get(m) is not None:
                self.channels.add(m)

        res = MinuteResult(v=v, ctx=ctx, evals=self._evaluate_norms(v, ctx))
        raw, source, res.env, res.ppco2_60, hard_dirs = self.detector.evaluate(v, ctx, res.evals)
        self.window.append(res)

        cls = self._classify(classifier)
        if cls is not None:
            res.pattern, res.p = cls
        if self.incident is None and cls and cls[0] not in ("normal", "sensor_artifact") and cls[1] >= PATTERN_P_WATCH:
            self._pattern_streak += 1
        else:
            self._pattern_streak = 0
        if raw == USUAL and self._pattern_streak >= PATTERN_WATCH_MIN:
            raw, source = WATCH, "pattern"  # the model alone never goes above Watch

        prev_level = self.detector.level
        res.raw, res.source = raw, source
        res.level = self.detector.apply_hysteresis(raw)
        if res.level != prev_level:
            self._events.append(LevelChanged(self.crew_id, res.level, self.critical_acked, v.history))

        self._track_incident(res, hard_dirs, cls, actions)
        res.learn_mask = self._learn(v, ctx, res.evals)
        self._track_learning(v)
        self._events.append(MinuteClosed(self.crew_id, res))
        return res

    def _evaluate_norms(self, v: MinuteValues, ctx: int) -> dict[str, MetricEval]:
        evals: dict[str, MetricEval] = {}
        norm_ctx = ctx if ctx != CTX_OFF else CTX_REST  # show the resting band while off
        for m in BASELINE_METRICS:
            x = v.get(m)
            norm = self.baseline.norm(m, norm_ctx, v.ts)
            e = MetricEval(learning=norm is None or norm.learning)
            if norm is not None and not norm.learning:
                e.lo, e.hi = norm.band
                e.med = norm.med
                if x is not None and ctx != CTX_OFF:
                    e.z = (x - norm.med) / norm.sig
            evals[m] = e
        return evals

    def _classify(self, classifier: PatternClassifierProto | None) -> tuple[str, float] | None:
        if classifier is None or len(self.window) < PATTERN_WINDOW_MIN:
            return None
        win = list(self.window)[-PATTERN_WINDOW_MIN:]
        if win[-1].v.ts - win[0].v.ts != (PATTERN_WINDOW_MIN - 1) * 60:
            return None  # needs 10 minutes in a row
        return classifier.classify(build_features(win, self.detector.press_median()))

    def _learn(self, v: MinuteValues, ctx: int, evals: dict[str, MetricEval]) -> int:
        """§6.5. After warm-up only calm minutes without an open incident go in,
        otherwise a week of hypoxia would become the norm."""
        mask = 0
        if ctx == CTX_OFF:
            return mask
        for m in BASELINE_METRICS:
            x = v.get(m)
            if x is None:
                continue
            e = evals[m]
            if e.learning or (e.z is not None and abs(e.z) < LEARN_MAX_ABS_Z and self.incident is None):
                self.baseline.admit(m, ctx, v.ts, x)
                mask |= LEARN_BIT[m]
        return mask

    def _track_learning(self, v: MinuteValues) -> None:
        ls = self.baseline.learn_state()
        if ls.state != self.learn.state or min(ls.days, 7) != min(self.learn.days, 7):
            became_learned = ls.state == "learned" and self.learn.state != "learned"
            self.learn = ls
            self._events.append(BaselineStateChanged(self.crew_id, ls.state, ls.days, ls.ready_pct, v.history))
            if became_learned:
                self._open_notice(KEY_BASELINE_LEARNED, v.ts, v.history)
        else:
            self.learn = ls

    # --- incident (§7.5) ---

    def _deviating(self, res: MinuteResult, hard_dirs: dict[str, str]) -> list[IncidentMetric]:
        v = res.v
        prev = {x.m: x for x in self.incident.metrics} if self.incident else {}
        out: list[IncidentMetric] = []
        for m in LEVEL_METRICS:
            e, x = res.evals[m], v.get(m)
            if x is None:
                continue
            by_z = e.evaluated and z_counts(m, e.z) and abs(e.z) >= Z_WATCH  # type: ignore[arg-type]
            if not (e.hard or by_z):
                continue
            direction = hard_dirs.get(m) or ("up" if (e.z or 0) > 0 else "down")
            out.append(self._metric(m, x, e.lo, e.hi, e.z, direction, e.hard, prev, v.ts))
        for m in _ENV_METRICS:
            lvl = res.env.get(m, 0)
            x = res.ppco2_60 if m == "ppco2" else v.press_hpa
            if lvl and x is not None:
                out.append(self._metric(m, x, None, None, None, "up" if m == "ppco2" else "down", lvl, prev, v.ts))
        return out

    def _metric(self, m, x, lo, hi, z, direction, hard, prev, ts) -> IncidentMetric:
        cutoff = ts - (SLOPE_WINDOW_MIN - 1) * 60
        pts = [(r.v.ts, r.v.get(m)) for r in self.window if r.v.ts >= cutoff and r.v.get(m) is not None]
        slope = slope_per_min(pts)  # type: ignore[arg-type]
        since = prev[m].since_ts if m in prev else ts
        return IncidentMetric(m=m, value=x, lo=lo, hi=hi, z=z, slope_per_min=slope, since_ts=since,
                              trend=_trend(m, slope), direction=direction, hard=hard)

    @staticmethod
    def _primary(metrics: list[IncidentMetric], source: str | None, current: str | None) -> IncidentMetric | None:
        """Hard limit first, then the largest |z| (§7.5)."""
        body = [x for x in metrics if x.m not in _ENV_METRICS]
        env = [x for x in metrics if x.m in _ENV_METRICS]
        hard = [x for x in body if x.hard]
        if hard:
            return max(hard, key=lambda x: (x.hard, abs(x.z or 0)))
        if source == "env" and env:
            return max(env, key=lambda x: x.hard)
        if body:
            return max(body, key=lambda x: abs(x.z or 0))
        if env:
            return env[0]
        return next((x for x in metrics if x.m == current), None)

    def _track_incident(self, res: MinuteResult, hard_dirs, cls, actions: ActionLibrary) -> None:
        v, inc = res.v, self.incident
        if res.level == USUAL:
            if inc is not None:
                inc.level, inc.ts_end, inc.ts_update = USUAL, v.ts, v.ts
                self.incident = None
                self._events.append(AlertChanged(self.crew_id, inc, False, v.history))
            return

        created = inc is None
        if inc is None:
            inc = self.incident = AlertEntity(
                crew_id=self.crew_id, key=KEY_INCIDENT, source=res.source or "baseline",
                ts_start=v.ts, ts_update=v.ts,
            )
        prev_level = inc.level
        inc.level = res.level
        inc.peak_level = max(inc.peak_level, res.level)
        inc.ts_update = v.ts
        inc.ctx = res.ctx
        if res.source and res.raw >= res.level:
            inc.source = res.source
        metrics = self._deviating(res, hard_dirs)
        if metrics:
            inc.metrics = metrics
        primary = self._primary(inc.metrics, res.source, inc.primary)
        inc.primary = primary.m if primary else inc.primary

        if cls is not None and cls[0] != "normal":
            inc.pattern, inc.p = cls
        elif inc.p is None:
            ruled = pattern_by_rule(inc.primary, primary.direction if primary else None, res.ctx)
            inc.pattern = ruled or inc.pattern

        if created or res.level > prev_level:
            summary = self._summary(inc, actions)
            inc.text = compose(summary, actions).as_dict()
            inc.text_src = "template"
            inc.text_rev += 1
            self._events.append(AlertChanged(self.crew_id, inc, created, v.history))
            if not v.history:
                self._events.append(NarrationRequested(self.crew_id, inc, inc.text_rev, summary))
        else:
            self._events.append(AlertChanged(self.crew_id, inc, False, v.history))

    def _summary(self, inc: AlertEntity, actions: ActionLibrary) -> NarrationInput:
        last = self.last
        metrics = []
        for x in inc.metrics:
            if x.m in _ENV_METRICS and x.m not in self.channels:
                continue
            limit = _ppco2_limit(x.hard) if x.m == "ppco2" else HARD_LIMIT_QUOTE.get((x.m, x.direction or "")) if x.hard else None
            usual = (rnd(x.m, x.lo), rnd(x.m, x.hi)) if x.lo is not None and x.hi is not None else None
            metrics.append(NarrationMetric(x.m, rnd(x.m, x.value), usual, x.trend, x.direction, limit))  # type: ignore[arg-type]
        env: dict[str, object] = {}
        if "ppco2" in self.channels and last is not None and last.v.ppco2 is not None:
            env["ppco2"] = rnd("ppco2", last.ppco2_60 if last.ppco2_60 is not None else last.v.ppco2)
        if "press" in self.channels and last is not None:
            env["pressure"] = "falling" if last.env.get("press") else "stable"
        since = (inc.ts_update - inc.ts_start) // 60
        return NarrationInput(
            pattern=inc.pattern, p=None if inc.p is None else round(inc.p, 2),
            severity=inc.peak_level, ctx=CTX_NAMES.get(inc.ctx) if inc.ctx is not None else None,
            since_min=since, primary=inc.primary, metrics=tuple(metrics), env=env,
            symptoms=self.symptoms, actions=actions.keys_for(inc.pattern, inc.peak_level),
        )

    # --- commands from outside the minute loop ---

    def ack(self, alert_id: int, now_ts: int) -> AlertEntity | None:
        target = next((a for a in self.open_alerts() if a.id == alert_id), None)
        if target is None:
            return None
        target.ack_ts = now_ts
        target.ts_update = now_ts
        if not target.is_incident:
            target.ts_end = now_ts  # a note is done once read
            self.notices.pop(target.key, None)
        self._events.append(AlertChanged(self.crew_id, target, False, False))
        if target.is_incident:
            self._events.append(LevelChanged(self.crew_id, self.level, self.critical_acked, False))
        return target

    def set_llm_text(self, alert_id: int, text_rev: int, text: dict) -> bool:
        inc = self.incident
        if inc is None or inc.id != alert_id or inc.text_rev != text_rev:
            return False  # closed or re-templated meanwhile
        inc.text, inc.text_src = text, "llm"
        self._events.append(AlertChanged(self.crew_id, inc, False, False))
        return True

    def ensure_checkin_notice(self, day: str, filed: bool, now_ts: int) -> None:
        key = CHECKIN_KEY_PREFIX + day
        for k in [k for k in self.notices if k.startswith(CHECKIN_KEY_PREFIX) and k != key]:
            self._close_notice(k, now_ts)
        if filed:
            self._close_notice(key, now_ts)
        elif key not in self.notices:
            self._open_notice(key, now_ts, False)

    def _open_notice(self, key: str, ts: int, history: bool) -> None:
        n = AlertEntity(crew_id=self.crew_id, key=key, source="system", ts_start=ts, ts_update=ts)
        self.notices[key] = n
        self._events.append(AlertChanged(self.crew_id, n, True, history))

    def _close_notice(self, key: str, ts: int) -> None:
        n = self.notices.pop(key, None)
        if n is not None:
            n.ts_end, n.ts_update = ts, ts
            self._events.append(AlertChanged(self.crew_id, n, False, False))

    # --- restart (§6.6, §13) ---

    def restore(self, rows: list[dict], open_alerts: list[AlertEntity]) -> None:
        for row in rows:
            r = MinuteResult.from_row(row)
            for m, bit in LEARN_BIT.items():
                x = r.v.get(m)
                if r.learn_mask & bit and x is not None:
                    self.baseline.admit(m, r.ctx, r.v.ts, x)
            if r.ctx != CTX_OFF:
                self.baseline.note_day(r.v.ts)
                d = r.v.ts // DAY
                self.data_min_by_day[d] = self.data_min_by_day.get(d, 0) + 1
            for m in _CHANNELS:
                if r.v.get(m) is not None:
                    self.channels.add(m)
            self.detector.feed_env(r.v)
            self.window.append(r)
        if rows:
            last = self.window[-1]
            self.detector.level = last.level
            self.context.reset_to(last.v.ts)
            self.day = last.v.ts // DAY
            self.baseline.recalc(last.v.ts)
            self.learn = self.baseline.learn_state()
        for a in open_alerts:
            if a.is_incident:
                self.incident = a
                self.detector.level = max(self.detector.level, a.level)
            else:
                self.notices[a.key] = a

    def reset(self) -> None:
        self.__init__(self.crew_id)

