"""API-first FDD client with a local-engine fallback."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import httpx
import pandas as pd

DEFAULT_API_URL = os.getenv("FDD_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("FDD_API_TIMEOUT", "8"))


class FDDService:
    """Call the FastAPI service when it is up, otherwise use ``FDDEngine``."""

    def __init__(self, api_url: str = DEFAULT_API_URL):
        self.api_url = api_url.rstrip("/")
        self._local_engine = None
        self._local_scenarios = None

    def health(self) -> Optional[dict]:
        try:
            response = httpx.get(f"{self.api_url}/health", timeout=1.5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
        return None

    @property
    def mode(self) -> str:
        return "api" if self.health() else "local"

    def _engine(self):
        if self._local_engine is None:
            from .fdd.inference import FDDEngine

            self._local_engine = FDDEngine()
        return self._local_engine

    def _scenarios(self):
        if self._local_scenarios is None:
            from .studies.synthetic.scenarios import SyntheticScenarios

            self._local_scenarios = SyntheticScenarios(self._engine())
        return self._local_scenarios

    def simulate_cycle(
        self,
        T_source: float = 7.0,
        T_sink: float = 40.0,
        speed_ratio: float = 0.7,
        fault_type: str = "Normal",
        severity: Optional[float] = None,
        **fault_overrides,
    ) -> Tuple[dict, str]:
        if self.health() is None:
            result = self._scenarios().simulate_cycle(
                T_source=T_source,
                T_sink=T_sink,
                speed_ratio=speed_ratio,
                fault_type=fault_type,
                severity=severity,
                **fault_overrides,
            )
            return result, "local"
        payload = {
            "T_source": T_source,
            "T_sink": T_sink,
            "speed_ratio": speed_ratio,
            "fault_type": fault_type,
            "severity": severity,
        }
        response = httpx.post(
            f"{self.api_url}/simulate", json=payload, timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json(), "api"

    def predict(self, features: Dict[str, float]) -> Tuple[dict, str]:
        if self.health() is None:
            return self._engine().predict(features), "local"
        response = httpx.post(
            f"{self.api_url}/predict",
            json={"features": features},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json(), "api"

    def live_trace(
        self,
        T_source: float = 7.0,
        T_sink: float = 40.0,
        speed_ratio: float = 0.7,
        fault_type: str = "Condenser_Fouling",
        inject_at: int = 25,
        n_points: int = 60,
        severity_final: float = 0.40,
    ) -> Tuple[pd.DataFrame, str]:
        if self.health() is None:
            return (
                self._scenarios().live_trace(
                    T_source=T_source,
                    T_sink=T_sink,
                    speed_ratio=speed_ratio,
                    fault_type=fault_type,
                    inject_at=inject_at,
                    n_points=n_points,
                    severity_final=severity_final,
                ),
                "local",
            )
        payload = {
            "T_source": T_source,
            "T_sink": T_sink,
            "speed_ratio": speed_ratio,
            "fault_type": fault_type,
            "inject_at": inject_at,
            "n_points": n_points,
            "severity_final": severity_final,
        }
        response = httpx.post(
            f"{self.api_url}/live", json=payload, timeout=max(TIMEOUT, 20)
        )
        response.raise_for_status()
        return pd.DataFrame(response.json()["trace"]), "api"

    def class_names(self) -> List[str]:
        health = self.health()
        if health and "classes" in health:
            return list(health["classes"])
        return list(self._engine().class_names)
