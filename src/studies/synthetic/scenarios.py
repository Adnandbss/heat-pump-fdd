"""Synthetic-study scenarios: inject a fault, then ask the engine to diagnose."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.data_generator import FaultDataGenerator, FaultType
from src.features import cycle_to_features
from src.simulator import CycleResults, HeatPumpSimulator

FAULT_PARAM_MAP = {
    "Normal": {},
    "Condenser_Fouling": {"condenser_fouling": 0.40},
    "Evaporator_Fouling": {"evaporator_fouling": 0.25},
    "Refrigerant_Undercharge": {"refrigerant_charge": 0.80},
    "Condenser_Fan_Fault": {"fan_cond_ratio": 0.55},
    "Evaporator_Fan_Fault": {"fan_evap_ratio": 0.55},
}


class SyntheticScenarios:
    """Build labelled synthetic cycles for the demo (`/simulate`, `/live`)."""

    def __init__(self, engine, simulator=None, random_seed: int = 42):
        self.engine = engine
        self.simulator = simulator or HeatPumpSimulator()
        self.generator = FaultDataGenerator(
            simulator=self.simulator, random_seed=random_seed
        )

    def simulate_cycle(
        self,
        T_source: float = 7.0,
        T_sink: float = 40.0,
        speed_ratio: float = 0.7,
        fault_type: str = "Normal",
        severity: Optional[float] = None,
        **fault_overrides,
    ) -> dict:
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
        diagnosis = self.engine.predict(features)
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
