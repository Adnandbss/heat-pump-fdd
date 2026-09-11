"""Pydantic contracts for the Heat Pump FDD API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class FaultLabel(str, Enum):
    """Labels the trained classifier can emit (and inject)."""

    NORMAL = "Normal"
    CONDENSER_FOULING = "Condenser_Fouling"
    EVAPORATOR_FOULING = "Evaporator_Fouling"
    REFRIGERANT_UNDERCHARGE = "Refrigerant_Undercharge"
    CONDENSER_FAN_FAULT = "Condenser_Fan_Fault"
    EVAPORATOR_FAN_FAULT = "Evaporator_Fan_Fault"


ChallengeStatus = Literal["On Going", "Complete"]


class FeatureVector(BaseModel):
    """24-d Li–Braun residual vector consumed by the classifier."""

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
    pressure_ratio: float
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


class StatsResponse(BaseModel):
    fault_type: str
    label: str
    confidence: float
    probabilities: Dict[str, float]
    COP: float
    P_cond: float
    P_evap: float
    T_discharge: float
    superheat: float
    subcooling: float
    model: str


class ClassShare(BaseModel):
    name: str
    value: int
    share: float


class OverviewResponse(BaseModel):
    total: int
    classes: List[ClassShare]
    f1: Optional[float] = None
    accuracy: Optional[float] = None


class ActivityResponse(BaseModel):
    fault_type: str
    inject_at: int
    trace: List[LiveTracePoint]


class Challenge(BaseModel):
    id: str
    title: str
    description: str
    injected: str
    predicted: str
    confidence: float
    status: ChallengeStatus
    progress: int = Field(ge=0, le=100)


class ChallengesResponse(BaseModel):
    challenges: List[Challenge]


class Scenario(BaseModel):
    title: str
    fault_type: str
    params: Dict[str, float] = Field(default_factory=dict)
    description: str


class ModelCard(BaseModel):
    name: str
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    f1_per_class: Dict[str, float] = Field(default_factory=dict)
    n_samples: Optional[int] = None
    n_features: Optional[int] = None
    calibrated: bool = True
    coolprop: bool = True


class CatalogResponse(BaseModel):
    classes: List[str]
    features: List[str]
    faults: List[str]
    scenarios: List[Scenario]
    model: ModelCard


class ModelComparisonRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    Model: str
    Accuracy: float
    Precision: float
    Recall: float
    F1_Score: float = Field(validation_alias="F1 Score", serialization_alias="F1 Score")


class ConfusionMatrix(BaseModel):
    labels: List[str]
    matrix: List[List[float]]


class FeatureImportance(BaseModel):
    feature: str
    importance: float


class ClassF1(BaseModel):
    name: str
    f1: float


class ModelsResponse(BaseModel):
    metadata: Dict[str, Any]
    comparison: List[ModelComparisonRow]
    confusion: ConfusionMatrix
    importance: List[FeatureImportance]
    f1_per_class: List[ClassF1]


class ColumnStats(BaseModel):
    mean: float
    std: float
    min: float
    max: float


class DatasetResponse(BaseModel):
    n_samples: int
    n_classes: int
    normal_share: float
    counts: Dict[str, int]
    describe: Dict[str, ColumnStats]
    columns: List[str]


class BoxStats(BaseModel):
    name: str
    min: float
    q1: float
    median: float
    q3: float
    max: float
    mean: float


class DistributionResponse(BaseModel):
    feature: str
    boxes: List[BoxStats]


class ScatterPoint(BaseModel):
    x: float
    y: float
    fault_type: str


class ScatterResponse(BaseModel):
    x: str
    y: str
    points: List[ScatterPoint]


class MatrixResponse(BaseModel):
    labels: List[str]
    matrix: List[List[float]]


class SaturationPoint(BaseModel):
    T: float
    P: float
    h_liq: float
    h_vap: float


class PhCyclePoint(BaseModel):
    name: str
    h: float
    P: float


class EnvelopeZone(BaseModel):
    T_evap: List[float]
    T_cond: List[float]


class Envelope(BaseModel):
    normal: EnvelopeZone
    extended: EnvelopeZone


class PhResponse(BaseModel):
    coolprop: bool
    P_evap: float
    P_cond: float
    COP: float
    saturation: List[SaturationPoint]
    cycle: List[PhCyclePoint]
    envelope: Envelope


class PhOverlay(BaseModel):
    T_evap: float
    T_cond: float
    P_evap: float
    P_cond: float
    COP: float
    cycle: List[PhCyclePoint]


class PhCompareResponse(BaseModel):
    coolprop: bool
    scenario: str
    saturation: List[SaturationPoint]
    nominal: PhOverlay
    condenser: Optional[PhOverlay] = None
    evaporator: Optional[PhOverlay] = None


class CopCurvePoint(BaseModel):
    T_amb: float
    carnot: float
    estimated: float


class CopMeasuredPoint(BaseModel):
    T_amb: float
    COP: float


class CopResponse(BaseModel):
    curves: List[CopCurvePoint]
    measured: List[CopMeasuredPoint]


class SweepPoint(BaseModel):
    T_evap: float
    T_cond: float
    P_evap: float
    P_cond: float
    tau: float
    COP: float
    W_comp: float
    Q_cond: float
    Q_evap: float
    T_dis: float
    load: Optional[float] = None
    t_source: Optional[float] = None


class SweepResponse(BaseModel):
    kind: str
    coolprop: bool
    points: List[SweepPoint]
    deltas: Dict[str, float]
    headline: str


class AshraeRow(BaseModel):
    T: float
    ashrae: float
    coolprop: float
    error_pct: float


class AshraeResponse(BaseModel):
    coolprop: bool
    rows: List[AshraeRow]


class AmbientHeatmapResponse(BaseModel):
    x_labels: List[str]
    y_labels: List[str]
    matrix: List[List[int]]
