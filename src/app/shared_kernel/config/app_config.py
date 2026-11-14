from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.app.shared_kernel.config.infra_configs import DatabaseConfig


ATPath = Annotated[str, StringConstraints(max_length=500, pattern=r"^[^\x00-\x1f]*$")]


class AppConfig(BaseSettings):
    """Environment variables from BACKEND_TZ §14, plus a few for RadLab."""

    # empty values in .env mean "use the default", as in the CRM configs
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)  # POSTGRES_*
    vdev_url: Annotated[str, StringConstraints(max_length=500)] = "http://localhost:8100"
    ollama_url: Annotated[str, StringConstraints(max_length=500)] = ""  # empty -> LLM off
    ollama_model: Annotated[str, StringConstraints(max_length=100, pattern=r"^[\w.:\-/]+$")] = "vigil-narrator"
    llm_timeout_s: float = Field(default=5.0, gt=0, le=60)
    pattern_model: ATPath = "ml/models/pattern.json"  # empty or missing -> rule (§8.3)
    pattern_meta: ATPath = "ml/models/pattern_meta.json"
    actions_file: ATPath = "docs/actions.yaml"
    cors_origin: Annotated[str, StringConstraints(max_length=500)] = "*"
    radlab_dir: ATPath = "data/radlab"
    radlab_instrument: Annotated[str, StringConstraints(max_length=50)] = ""  # empty -> most frequent
    # TODO: RadLab does not state the unit next to `absorbed_dose_rate`; confirm
    # against the OSDR docs and fix the default. [проверить]
    radlab_rate_unit: Literal["uGy/h", "uGy/min", "mGy/day"] = "uGy/h"
    mission_start: date | None = None  # flight day 1; empty -> first day with data
    link_timeout_s: float = Field(default=10.0, gt=0, le=600)
    host: Annotated[str, StringConstraints(max_length=100)] = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
