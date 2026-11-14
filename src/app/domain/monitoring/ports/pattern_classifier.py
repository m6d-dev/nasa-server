from typing import Protocol


class PatternClassifierProto(Protocol):
    """XGBoost from ML (BACKEND_TZ §8.1). Implemented in infra; absent → rule."""

    def classify(self, features: dict[str, float]) -> tuple[str, float] | None: ...
