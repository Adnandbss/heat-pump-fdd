"""Payloads for GET /api/evidence/* — numbers come from results.csv."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProtocolRef(BaseModel):
    experiment: str
    protocol: str
    reference: str
    features: str = ""
    model: str = ""


class SummaryCard(BaseModel):
    key: str
    label: str
    value: str
    protocol: Optional[ProtocolRef] = None


class EvidenceSummary(BaseModel):
    n_experiments: int
    n_measurements: int
    n_protocols: int
    headline_value: Optional[float] = None
    headline_percent: Optional[float] = None
    headline_protocol: Optional[ProtocolRef] = None
    cards: List[SummaryCard]


class LadderRung(BaseModel):
    value: float
    percent: float
    cause: str
    band: str
    majority: bool = False
    protocol: ProtocolRef


class EvidenceLadder(BaseModel):
    rungs: List[LadderRung]
    majority: Optional[float] = None


class ProtocolSlopePoint(BaseModel):
    features: str
    random_cv: Optional[float] = None
    lomo: Optional[float] = None
    protocol_cv: Optional[ProtocolRef] = None
    protocol_lomo: Optional[ProtocolRef] = None


class EvidenceProtocols(BaseModel):
    series: List[ProtocolSlopePoint]


class ReferencePoint(BaseModel):
    family: str
    facet: str
    conditioning: str
    dmin: float
    accuracy: float
    protocol: ProtocolRef


class EvidenceReferences(BaseModel):
    points: List[ReferencePoint]
    majority: Optional[float] = None
    annotation_dmin0: Optional[ReferencePoint] = None
    annotation_dmin05: Optional[ReferencePoint] = None
    badge: Optional[ProtocolRef] = None


class PerClassScores(BaseModel):
    display: str
    simulated: Optional[float] = None
    target: Optional[float] = None
    transferred: Optional[float] = None


class EvidencePerClass(BaseModel):
    rows: List[PerClassScores]
    notes: List[str]
    protocols: Dict[str, ProtocolRef]


class RunRow(BaseModel):
    experiment: str
    protocol: str
    reference: str
    features: str
    model: str
    label: str
    metric: str
    value: float
    n: Optional[int] = None
    note: str = ""


class EvidenceRuns(BaseModel):
    total: int
    offset: int
    limit: int
    rows: List[RunRow]
    csv_path: str = "outputs/results.csv"
    experiments: List[str] = Field(default_factory=list)
    protocols: List[str] = Field(default_factory=list)
    models: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)


class EvidenceConfusion(BaseModel):
    protocol: str
    labels: List[str]
    matrix: List[List[float]]
    source: str


class WilsonInterval(BaseModel):
    low: float
    high: float


class DomainBar(BaseModel):
    key: str
    label: str
    accuracy: float
    n: Optional[int] = None
    wilson: Optional[WilsonInterval] = None
    protocol: ProtocolRef


class SeverityPair(BaseModel):
    key: str
    label: str
    binary: Optional[float] = None
    multiclass: Optional[float] = None
    n_binary: Optional[int] = None
    n_multiclass: Optional[int] = None
    binary_protocol: Optional[ProtocolRef] = None
    multiclass_protocol: Optional[ProtocolRef] = None


class EvidenceDomain(BaseModel):
    domain: List[DomainBar]
    severity: List[SeverityPair]
    caption: str
    badge: ProtocolRef


class FeatureSlopePoint(BaseModel):
    features: str
    holdout: Optional[float] = None
    domain: Optional[float] = None
    protocol_holdout: Optional[ProtocolRef] = None
    protocol_domain: Optional[ProtocolRef] = None


class EvidenceFeatures(BaseModel):
    series: List[FeatureSlopePoint]
    note: str
    badge: ProtocolRef


class RulesBar(BaseModel):
    model: str
    label: str
    accuracy: Optional[float] = None
    protocol: Optional[ProtocolRef] = None


class EvidenceRules(BaseModel):
    bars: List[RulesBar]
    majority: Optional[float] = None
    majority_protocol: Optional[ProtocolRef] = None
    badge: ProtocolRef
