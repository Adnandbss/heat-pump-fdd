"""Shared inference engine: load the trained FDD model and diagnose cycles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from .data_generator import FaultDataGenerator, FaultType
from .features import FEATURE_COLUMNS, SCENARIOS, cycle_to_features
from .ml_models import FDDClassifier
from .simulator import CycleResults, HeatPumpSimulator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = ROOT / "models" / "fdd_classifier.joblib"
DEFAULT_METADATA_PATH = ROOT / "models" / "metadata.json"

FAULT_PARAM_MAP = {
    "Normal": {},
    "Condenser_Fouling": {"condenser_fouling": 0.40},
    "Evaporator_Fouling": {"evaporator_fouling": 0.25},
    "Refrigerant_Undercharge": {"refrigerant_charge": 0.80},
    "Condenser_Fan_Fault": {"fan_cond_ratio": 0.55},
    "Evaporator_Fan_Fault": {"fan_evap_ratio": 0.55},
}


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
        self.simulator = HeatPumpSimulator()
        self.generator = FaultDataGenerator(simulator=self.simulator, random_seed=42)

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

    def simulate_cycle(
        self,
        T_source: float = 7.0,
        T_sink: float = 40.0,
        speed_ratio: float = 0.7,
        fault_type: str = "Normal",
        severity: Optional[float] = None,
        **fault_overrides,
    ) -> Dict:
        params = dict(FAULT_PARAM_MAP.get(fault_type, {}))
        if severity is not None and fault_type != "Normal":
            try:
                enum_fault = FaultType(fault_type)
                params = self.generator._apply_fault(enum_fault, float(severity))
            except ValueError:
                pass
        params.update(fault_overrides)
        result: CycleResults = self.simulator.simulate_cycle(
            T_source=T_source,
            T_sink=T_sink,
            speed_ratio=speed_ratio,
            **params,
        )
        features = cycle_to_features(
            result,
            T_source,
            T_sink,
            speed_ratio,
            self.simulator.capacity_nom,
            simulator=self.simulator,
        )
        diagnosis = self.predict(features)
        return {
            "conditions": {
                "T_source": T_source,
                "T_sink": T_sink,
                "speed_ratio": speed_ratio,
                "injected_fault": fault_type,
            },
            "cycle": {
                "P_evap": result.P_evap,
                "P_cond": result.P_cond,
                "T_evap": result.T_evap,
                "T_cond": result.T_cond,
                "T_suction": result.T_suction,
                "T_discharge": result.T_discharge,
                "superheat": result.superheat,
                "subcooling": result.subcooling,
                "compression_ratio": result.compression_ratio,
                "W_comp": result.W_comp,
                "Q_cond": result.Q_cond,
                "COP": result.COP,
            },
            "features": features,
            "diagnosis": diagnosis,
        }

    def live_trace(
        self,
        T_source: float = 7.0,
        T_sink: float = 40.0,
        speed_ratio: float = 0.7,
        fault_type: str = "Condenser_Fouling",
        inject_at: int = 25,
        n_points: int = 60,
        severity_final: float = 0.40,
    ) -> pd.DataFrame:
        """Build a telemetry series with a fault injected after ``inject_at``."""
        rows = []
        for t in range(n_points):
            if t < inject_at or fault_type == "Normal":
                current_fault = "Normal"
                severity = 0.0
            else:
                current_fault = fault_type
                progress = (t - inject_at) / max(n_points - inject_at, 1)
                severity = min(severity_final, 0.12 + progress * severity_final)
            payload = self.simulate_cycle(
                T_source=T_source + np.sin(t / 8.0) * 0.4,
                T_sink=T_sink,
                speed_ratio=speed_ratio,
                fault_type=current_fault,
                severity=severity,
            )
            rows.append(
                {
                    "t": t,
                    "injected_fault": current_fault,
                    "severity": severity,
                    "predicted": payload["diagnosis"]["label"],
                    "confidence": payload["diagnosis"]["confidence"],
                    **payload["cycle"],
                }
            )
        return pd.DataFrame(rows)
