import pytest

from src.app.domain.monitoring.constants.thresholds import CTX_ACTIVE, CTX_OFF, CTX_REST, CTX_SLEEP
from src.app.domain.monitoring.entities.minute import MinuteValues, ppco2_mmhg
from src.app.domain.monitoring.services.aggregation import MinuteAccumulator, fold_seconds
from src.app.domain.monitoring.services.baseline import PersonalBaseline
from src.app.domain.monitoring.services.context import ContextClassifier
from src.app.domain.monitoring.services.levels import LevelDetector
from src.app.domain.monitoring.services.stats import robust_stats
from src.vigil_types.ingest.frame import FLAG_WORN, TYPE_SECOND, Frame

T0 = 1794614400


def sec(ts: int, hr: float | None = 60.0, sqi: int = 90) -> Frame:
    return Frame(type=TYPE_SECOND, dev_id=1, ts=ts, hr=hr, sqi=sqi, flags=FLAG_WORN, act_mg=10)


def test_minute_is_median_of_valid_seconds():
    frames = [sec(T0 + i, hr=60 + (i % 3)) for i in range(60)]
    m = fold_seconds(1, T0, frames)
    assert m.hr == 61 and m.valid_s == 60 and m.worn_frac == 1.0


def test_minute_with_fewer_than_20_valid_seconds_is_null():
    frames = [sec(T0 + i, sqi=90 if i < 19 else 30) for i in range(60)]
    assert fold_seconds(1, T0, frames).hr is None


def test_accumulator_closes_on_next_minute():
    acc = MinuteAccumulator(1)
    assert all(acc.add(sec(T0 + i)) is None for i in range(60))
    closed = acc.add(sec(T0 + 60))
    assert closed is not None and closed.ts == T0


def test_ppco2():
    assert ppco2_mmhg(5000, 1013.25) == pytest.approx(3.80, abs=0.005)
    assert ppco2_mmhg(5000, None) == pytest.approx(3.80, abs=0.005)
    assert ppco2_mmhg(None, 1000) is None


def _m(ts, act=20.0, hr=60.0, worn=1.0, sqi=90.0, training=False) -> MinuteValues:
    return MinuteValues(crew_id=1, ts=ts, act_mg=act, hr=hr, worn_frac=worn, sqi=sqi, training=training)


def test_context_cases():
    c = ContextClassifier()
    assert c.classify(_m(T0, worn=0.2), None) == CTX_OFF
    assert c.classify(_m(T0 + 60, act=80), None) == CTX_ACTIVE
    # five minutes of cool-down after exercise
    assert [c.classify(_m(T0 + 60 * k, act=20), None) for k in range(2, 8)] == [CTX_ACTIVE] * 5 + [CTX_REST]
    c2 = ContextClassifier()
    ctxs = [c2.classify(_m(T0 + 60 * k, act=3, hr=55), 60.0) for k in range(16)]
    assert ctxs[13] == CTX_REST and ctxs[14] == CTX_SLEEP  # 15 still minutes
    assert c2.classify(_m(T0 + 60 * 16, act=3, hr=90), 60.0) == CTX_REST  # pulse too high for sleep


def test_training_bit_is_active():
    assert ContextClassifier().classify(_m(T0, act=5, training=True), None) == CTX_ACTIVE


def test_norm_example_from_tz():
    med, sig = robust_stats([56, 58, 57, 60, 55, 57, 59], 3.0)
    assert (med, sig) == (57, 3.0)
    assert (66 - med) / sig == 3.0


def _baseline_with(n: int, days: int) -> PersonalBaseline:
    b = PersonalBaseline()
    per_day = -(-n // days)
    for i in range(n):
        d, k = divmod(i, per_day)
        b.admit("hr", CTX_REST, T0 + d * 86400 + 8 * 3600 + k * 60 % 3600, 60.0 + (i % 5))  # 08:00–09:00
    b.recalc(T0 + days * 86400)
    return b


def test_cell_not_ready_with_119_values():
    assert _baseline_with(119, 3).norm("hr", CTX_REST, T0 + 8 * 3600).learning
    assert not _baseline_with(120, 3).norm("hr", CTX_REST, T0 + 8 * 3600).learning


def test_cell_not_ready_with_two_days():
    assert _baseline_with(500, 2).norm("hr", CTX_REST, T0 + 8 * 3600).learning


def test_hysteresis_up_at_once_down_after_ten():
    d = LevelDetector()
    assert d.apply_hysteresis(3) == 3
    assert [d.apply_hysteresis(0) for _ in range(10)] == [3] * 9 + [2]
    assert [d.apply_hysteresis(0) for _ in range(10)] == [2] * 9 + [1]
