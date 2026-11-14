"""Demo panel → vdev. The server forwards these unchanged (BACKEND_TZ §11.10);
the shapes follow PLAN.md SIM-3 and are owned by EMB."""

from typing import Annotated, Literal

from pydantic import Field

from src.vigil_types.base import ATCrewId, BaseContract, Command, Query

ScenarioName = Literal[
    "hypoxia", "tachycardia_rest", "bradycardia", "fever_like", "hypercapnia",
    "depressurization", "sensor_off", "motion_artifact", "sleep_drift", "stop",
]


class SimScenarioCommand(Command):
    crew: ATCrewId
    name: ScenarioName
    severity: Annotated[int, Field(ge=1, le=3)] | None = None
    duration: Annotated[int, Field(ge=1, le=7 * 86400)] | None = None  # seconds


class SimSpeedCommand(Command):
    mode: Literal["live", "fast", "backfill"] | None = None
    k: Annotated[float, Field(gt=0, le=10000)] | None = None
    days: Annotated[int, Field(ge=1, le=30)] | None = None


class SimResetCommand(Command): ...


class SimStateQuery(Query): ...


class SimResponse(BaseContract):
    status: int
    body: dict | list | str | None


__all__ = ["SimScenarioCommand", "SimSpeedCommand", "SimResetCommand", "SimStateQuery", "SimResponse"]
