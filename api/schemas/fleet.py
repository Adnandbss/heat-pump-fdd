"""Payloads for GET /api/fleet — a simulated OEM fleet, triaged by the evidence policy."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EvidenceStatus = Literal["transfers", "does_not_transfer", "untested"]
FleetAction = Literal["dispatch", "engineering_review", "monitor", "no_action"]


class FleetEvidence(BaseModel):
    status: EvidenceStatus
    experiment: str
    protocol: str
    f1: Optional[float] = None
    n: Optional[int] = None


class FleetUnit(BaseModel):
    unit_id: str
    T_source: float
    T_sink: float
    speed_ratio: float
    diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: FleetEvidence
    action: FleetAction
    instruction: str
    priority: int
    ground_truth: str = Field(description="Injected fault. Exists only because the fleet is simulated.")
    ground_truth_severity: float


class FleetSummary(BaseModel):
    units: int
    dispatch: int
    engineering_review: int
    monitor: int
    no_action: int
    held_back: int = Field(
        description="Units the policy would dispatch with the evidence gate off, and does not with it on."
    )


class FleetPolicy(BaseModel):
    validated_only: bool
    evidence_experiment: str
    evidence_protocol: str
    evidence_f1_min: float
    confidence_min: float


class FleetResponse(BaseModel):
    notice: str
    seed: int
    policy: FleetPolicy
    summary: FleetSummary
    units: List[FleetUnit]
