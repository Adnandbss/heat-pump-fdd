"""Pydantic contracts for diagnosis routes."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FaultLabel(str, Enum):
    """Labels the trained classifier can emit (and inject)."""

    NORMAL = "Normal"
    CONDENSER_FOULING = "Condenser_Fouling"
    EVAPORATOR_FOULING = "Evaporator_Fouling"
    REFRIGERANT_UNDERCHARGE = "Refrigerant_Undercharge"
    REFRIGERANT_OVERCHARGE = "Refrigerant_Overcharge"
    CONDENSER_FAN_FAULT = "Condenser_Fan_Fault"
    EVAPORATOR_FAN_FAULT = "Evaporator_Fan_Fault"


class FeatureVector(BaseModel):
    """23-d cycle vector consumed by the classifier (P5: pressure_ratio dropped)."""

    model_config = ConfigDict(extra="forbid")

    T_ambient: float
    T_setpoint: float
    compressor_speed_ratio: float
    P_evap: float
    P_cond: float
    T_evap: float
    T_cond: float
    T_suction: float
    T_discharge: float
    superheat: float
    subcooling: float
    compression_ratio: float
    W_comp: float
    Q_cond: float
    COP: float
    delta_T_evap: float
    delta_T_cond: float
    capacity_ratio: float
    d_T_discharge: float
    d_superheat: float
    d_subcooling: float
    d_COP: float
    d_W_comp: float


class CycleState(BaseModel):
    P_evap: float
    P_cond: float
    T_evap: float
    T_cond: float
    T_suction: float
    T_discharge: float
    superheat: float
    subcooling: float
    compression_ratio: float
    W_comp: float
    Q_cond: float
    COP: float


class OperatingConditions(BaseModel):
    T_source: float
    T_sink: float
    speed_ratio: float
    injected_fault: str


class Diagnosis(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: Dict[str, float]


class PredictRequest(BaseModel):
    features: FeatureVector


class SimulateRequest(BaseModel):
    T_source: float = Field(7.0, description="Evaporator source temperature °C")
    T_sink: float = Field(40.0, description="Condenser sink temperature °C")
    speed_ratio: float = Field(0.7, ge=0.3, le=1.0)
    fault_type: FaultLabel = FaultLabel.NORMAL
    severity: Optional[float] = Field(None, ge=0.0, le=1.0)


class LiveRequest(BaseModel):
    T_source: float = 7.0
    T_sink: float = 40.0
    speed_ratio: float = Field(0.7, ge=0.3, le=1.0)
    fault_type: FaultLabel = FaultLabel.CONDENSER_FOULING
    inject_at: int = Field(25, ge=1, le=80)
    n_points: int = Field(60, ge=10, le=120)
    severity_final: float = Field(0.40, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    status: str
    model: str
    classes: List[str]


class SimulateResponse(BaseModel):
    conditions: OperatingConditions
    cycle: CycleState
    features: FeatureVector
    diagnosis: Diagnosis


class LiveTracePoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    t: int = Field(ge=0)
    injected_fault: str
    severity: float
    predicted: str
    confidence: float
    P_evap: float
    P_cond: float
    T_discharge: float
    superheat: float
    subcooling: float
    COP: float


class LiveResponse(BaseModel):
    trace: List[LiveTracePoint]
