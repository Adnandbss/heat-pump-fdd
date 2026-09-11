"""Shared inference engine: load a trained FDD model and diagnose a feature vector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Union

import pandas as pd

from .features import FEATURE_COLUMNS
from .ml_models import FDDClassifier

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = ROOT / "models" / "fdd_classifier.joblib"
DEFAULT_METADATA_PATH = ROOT / "models" / "metadata.json"


class FDDEngine:
    """Load-once classifier used by the dashboard and the API."""

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_MODEL_PATH,
        metadata_path: Union[str, Path] = DEFAULT_METADATA_PATH,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found at {self.model_path}. "
                "Run `python main_analysis.py` first."
            )
        self.classifier = FDDClassifier.load(str(self.model_path))
        self.metadata = {}
        if self.metadata_path.exists():
            self.metadata = json.loads(self.metadata_path.read_text())

    @property
    def class_names(self) -> List[str]:
        return list(self.classifier.class_names)

    @property
    def feature_names(self) -> List[str]:
        return list(self.classifier.feature_names or FEATURE_COLUMNS)

    def _frame(self, features: Union[Dict, pd.DataFrame]) -> pd.DataFrame:
        if isinstance(features, pd.DataFrame):
            df = features.copy()
        else:
            df = pd.DataFrame([features])
        missing = [c for c in self.feature_names if c not in df.columns]
        if missing:
            raise ValueError(f"Missing features: {missing}")
        return df[self.feature_names]

    def predict(self, features: Union[Dict, pd.DataFrame]) -> Dict:
        X = self._frame(features)
        label = str(self.classifier.predict(X)[0])
        proba = self.classifier.predict_proba(X)[0]
        probabilities = {
            name: float(p) for name, p in zip(self.class_names, proba)
        }
        return {
            "label": label,
            "confidence": float(max(proba)),
            "probabilities": probabilities,
        }
