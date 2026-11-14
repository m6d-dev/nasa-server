from dataclasses import dataclass

from src.app.domain.monitoring.entities.alert import AlertEntity
from src.app.domain.monitoring.entities.minute import MinuteResult
from src.app.domain.narration.entities.narration import NarrationInput


@dataclass(slots=True, frozen=True)
class DomainEvent:
    crew_id: int


@dataclass(slots=True, frozen=True)
class MinuteClosed(DomainEvent):
    result: MinuteResult


@dataclass(slots=True, frozen=True)
class DayChanged(DomainEvent):
    prev_day: int  # unix day number
    new_day: int
    history: bool


@dataclass(slots=True, frozen=True)
class LevelChanged(DomainEvent):
    level: int
    critical_acked: bool
    history: bool


@dataclass(slots=True, frozen=True)
class AlertChanged(DomainEvent):
    """Created, level/text changed, acknowledged or closed. Persist + /live."""

    alert: AlertEntity
    created: bool
    history: bool


@dataclass(slots=True, frozen=True)
class NarrationRequested(DomainEvent):
    """The template is already in place; an LLM may improve it in the background."""

    alert: AlertEntity
    text_rev: int
    summary: NarrationInput


@dataclass(slots=True, frozen=True)
class BaselineStateChanged(DomainEvent):
    state: str
    days: int
    ready_pct: int
    history: bool
