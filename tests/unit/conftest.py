import copy
import random

import pytest

from src.app.domain.monitoring.aggregates.crew_monitor import CrewMonitorAggregate
from src.app.domain.monitoring.entities.minute import MinuteValues
from src.app.infra.impls.model_files import load_actions

T0 = 1794614400  # 2026-11-14 00:00 UTC
ACTIONS = load_actions("docs/actions.yaml")


def calm(ts: int, rng: random.Random, **over) -> MinuteValues:
    """A resting minute of a healthy person: hr ~60, spo2 ~97.5, rr ~14, skin 33.5."""
    v = MinuteValues(
        crew_id=1, ts=ts,
        hr=60 + rng.gauss(0, 1.5), spo2=97.5 + rng.gauss(0, 0.4), rr=14 + rng.gauss(0, 0.6),
        skin_t=33.5 + rng.gauss(0, 0.1), co2_ppm=2500.0, press_hpa=1013.0, amb_t=22.0,
        act_mg=20.0, sqi=95.0, worn_frac=1.0, valid_s=60, kind=2, history=True,
    )
    for k, x in over.items():
        setattr(v, k, x)
    return v


def feed(agg: CrewMonitorAggregate, start: int, minutes: int, rng: random.Random, **over) -> int:
    ts = start
    for _ in range(minutes):
        agg.on_minute(calm(ts, rng, **over), None, ACTIONS)
        ts += 60
    agg.pull_events()
    return ts


@pytest.fixture(scope="session")
def _learned() -> tuple[CrewMonitorAggregate, int]:
    """8 days of calm rest minutes → the rest cells are ready."""
    rng = random.Random(7)
    agg = CrewMonitorAggregate(1)
    ts = feed(agg, T0 - 8 * 86400, 8 * 1440, rng)
    agg.baseline.recalc(ts)
    return agg, ts


@pytest.fixture
def learned(_learned) -> tuple[CrewMonitorAggregate, int]:
    agg, ts = _learned
    return copy.deepcopy(agg), ts
