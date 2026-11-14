from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class AlertText:
    what: str
    why: str
    action: tuple[str, ...]  # 1–3 lines, numbered on the Critical screen

    def as_dict(self) -> dict[str, Any]:
        return {"what": self.what, "why": self.why, "action": list(self.action)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AlertText":
        return cls(d["what"], d["why"], tuple(d.get("action") or ()))


@dataclass(slots=True, frozen=True)
class NarrationMetric:
    m: str
    value: float | int | None
    usual: tuple[float | int, float | int] | None
    trend: str
    direction: str | None
    limit: float | None = None


@dataclass(slots=True, frozen=True)
class NarrationInput:
    """The summary from PLAN.md §11.3. Everything the text may say is in here,
    already rounded, so an LLM answer can be checked number by number."""

    pattern: str | None
    p: float | None
    severity: int
    ctx: str | None
    since_min: int
    primary: str | None
    metrics: tuple[NarrationMetric, ...]
    env: dict[str, Any]  # only channels the device really sends
    symptoms: tuple[str, ...]
    actions: tuple[str, ...]  # keys from actions.yaml

    def as_llm_json(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern, "p": self.p, "severity": self.severity,
            "ctx": self.ctx, "since_min": self.since_min,
            "metrics": [
                {"m": x.m, "value": x.value, "usual": list(x.usual) if x.usual else None,
                 "trend": x.trend, **({"limit": x.limit} if x.limit is not None else {})}
                for x in self.metrics
            ],
            "env": self.env, "symptoms": list(self.symptoms), "actions": list(self.actions),
        }


@dataclass(slots=True, frozen=True)
class ActionLibrary:
    """docs/actions.yaml — written by people, the model only rephrases (PLAN §11.2)."""

    texts: dict[str, str] = field(default_factory=dict)
    by_pattern: dict[str, dict[int, tuple[str, ...]]] = field(default_factory=dict)

    def keys_for(self, pattern: str | None, severity: int) -> tuple[str, ...]:
        table = self.by_pattern.get(pattern or "default") or self.by_pattern.get("default") or {}
        sev = max(1, min(3, severity))
        while sev >= 1 and sev not in table:
            sev -= 1
        return table.get(sev, ())[:3]

    def text(self, key: str) -> str:
        return self.texts.get(key, key.replace("_", " ").capitalize() + ".")
