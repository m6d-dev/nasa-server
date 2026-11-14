"""Files from other team members: the XGBoost model (ML) and actions.yaml (D2).
Both are optional at start (BACKEND_TZ §2): missing → rule / built-in defaults."""

import json
import logging
from pathlib import Path

import yaml

from src.app.domain.monitoring.constants.thresholds import PATTERN_CLASSES
from src.app.domain.monitoring.ports.pattern_classifier import PatternClassifierProto
from src.app.domain.monitoring.services.features import FEATURE_NAMES
from src.app.domain.narration.entities.narration import ActionLibrary
from src.app.shared_kernel.utils.assertion import ensure_isimplementation

logger = logging.getLogger("vigil.models")


class XgbPatternClassifier(PatternClassifierProto):
    def __init__(self, booster, features: list[str], classes: list[str]) -> None:
        self._booster, self._features, self._classes = booster, features, classes

    def classify(self, features: dict[str, float]) -> tuple[str, float] | None:
        import numpy as np
        import xgboost as xgb

        row = np.asarray([[features.get(f, float("nan")) for f in self._features]], dtype=np.float32)
        probs = self._booster.predict(xgb.DMatrix(row, feature_names=self._features))[0]
        i = int(probs.argmax())
        return self._classes[i], float(probs[i])


def load_pattern_classifier(model_path: str, meta_path: str) -> PatternClassifierProto | None:
    if not model_path or not Path(model_path).is_file():
        logger.info("pattern model not found (%s): rule-based patterns", model_path or "-")
        return None
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("xgboost is not installed: rule-based patterns")
        return None
    meta = json.loads(Path(meta_path).read_text()) if Path(meta_path).is_file() else {}
    features = list(meta.get("features") or FEATURE_NAMES)
    classes = list(meta.get("classes") or PATTERN_CLASSES)
    unknown = set(features) - set(FEATURE_NAMES)
    if unknown:
        logger.error("pattern_meta.json names features we do not compute: %s", sorted(unknown))
        return None
    booster = xgb.Booster()
    booster.load_model(model_path)
    logger.info("pattern model loaded: %d features, %d classes", len(features), len(classes))
    return XgbPatternClassifier(booster, features, classes)


def load_actions(path: str) -> ActionLibrary:
    p = Path(path)
    if not p.is_file():
        logger.warning("actions file not found (%s): actions fall back to the report line", path)
        return ActionLibrary()
    doc = yaml.safe_load(p.read_text()) or {}
    texts = {str(k): str(v) for k, v in (doc.get("actions") or {}).items()}
    by_pattern = {
        str(pat): {int(sev): tuple(str(k) for k in keys) for sev, keys in (table or {}).items()}
        for pat, table in (doc.get("patterns") or {}).items()
    }
    missing = {k for t in by_pattern.values() for keys in t.values() for k in keys} - texts.keys()
    if missing:
        logger.warning("actions.yaml uses keys without text: %s", sorted(missing))
    return ActionLibrary(texts=texts, by_pattern=by_pattern)


ensure_isimplementation(XgbPatternClassifier, PatternClassifierProto)
