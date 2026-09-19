"""Pydantic contracts for dashboard and thermo routes."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.inference import LiveTracePoint

ChallengeStatus = Literal["On Going", "Complete"]


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
