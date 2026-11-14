import random

from src.app.domain.monitoring.constants.thresholds import CTX_OFF, LEARN_BIT
from src.app.domain.monitoring.events.monitoring_events import AlertChanged, NarrationRequested
from tests.unit.conftest import ACTIONS, calm


def step(agg, ts, rng, **over):
    return agg.on_minute(calm(ts, rng, **over), None, ACTIONS)


def test_learned_after_eight_days(learned):
    agg, _ = learned
    assert agg.learn.state == "learned"
    assert agg.incident is None and agg.level == 0


def test_z_watch_needs_five_minutes(learned):
    agg, ts = learned
    rng = random.Random(1)
    norm = agg.baseline.norm("hr", 2, ts)
    hr = norm.med + 2.2 * norm.sig  # |z| ≥ 2, < 3, below hard limits
    levels = [step(agg, ts + 60 * k, rng, hr=hr).level for k in range(5)]
    assert levels == [0, 0, 0, 0, 1]


def test_missing_minute_resets_streak(learned):
    agg, ts = learned
    rng = random.Random(1)
    norm = agg.baseline.norm("hr", 2, ts)
    hr = norm.med + 2.2 * norm.sig
    for k in range(4):
        step(agg, ts + 60 * k, rng, hr=hr)
    assert step(agg, ts + 60 * 5, rng, hr=hr).level == 0  # minute 4 is missing


def test_poisoning_guard(learned):
    agg, ts = learned
    norm = agg.baseline.norm("hr", 2, ts)
    res = step(agg, ts, random.Random(2), hr=norm.med + 3 * norm.sig)
    assert not res.learn_mask & LEARN_BIT["hr"]


def test_spo2_88_one_minute_is_critical_with_incident(learned):
    agg, ts = learned
    res = step(agg, ts, random.Random(3), spo2=88.0, history=False)
    assert res.level == 3
    inc = agg.incident
    assert inc is not None and inc.primary == "spo2" and inc.pattern == "hypoxia"
    assert inc.text and inc.text["what"] and inc.text["action"] and inc.text_src == "template"
    events = agg.pull_events()
    assert any(isinstance(e, AlertChanged) and e.created for e in events)
    assert any(isinstance(e, NarrationRequested) for e in events)


def test_incident_closes_when_level_returns(learned):
    agg, ts = learned
    rng = random.Random(4)
    step(agg, ts, rng, spo2=88.0)
    inc = agg.incident
    for k in range(1, 40):
        step(agg, ts + 60 * k, rng)
    assert agg.level == 0 and agg.incident is None and inc.ts_end is not None


def test_sensor_off_raises_nothing(learned):
    agg, ts = learned
    rng = random.Random(5)
    for k in range(20):
        res = step(agg, ts + 60 * k, rng, worn_frac=0.0, sqi=0.0, hr=None, spo2=None)
    assert res.ctx == CTX_OFF and agg.level == 0 and agg.incident is None


def test_exercise_hr_140_is_not_an_alarm(learned):
    agg, ts = learned
    rng = random.Random(6)
    for k in range(20):
        step(agg, ts + 60 * k, rng, hr=140.0, rr=24.0, act_mg=300.0)
    assert agg.level == 0 and agg.incident is None


def test_ack_keeps_level(learned):
    agg, ts = learned
    step(agg, ts, random.Random(7), spo2=88.0)
    agg.incident.id = 1
    assert agg.ack(1, ts + 30) is not None
    assert agg.level == 3 and agg.critical_acked
