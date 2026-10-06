"""Fleet triage for an OEM after-sales team, on a seeded simulated fleet."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from api import fleet_policy as policy
from api.deps import get_results, get_scenarios, get_settings
from api.errors import ArtifactMissing
from api.schemas.fleet import (
    FleetEvidence,
    FleetPolicy,
    FleetResponse,
    FleetSummary,
    FleetUnit,
)
from api.settings import Settings
from src.studies.synthetic.generator import FaultType
from src.studies.synthetic.scenarios import SyntheticScenarios

router = APIRouter(prefix="/api/fleet", tags=["fleet"])

NOTICE = (
    "Simulated demo fleet: units, conditions and faults come from the cycle simulator. "
    "Evidence statuses are read from outputs/results.csv."
)
HEALTHY_SHARE = 0.45
MAX_ATTEMPTS_PER_UNIT = 20


@dataclass(frozen=True)
class SimulatedUnit:
    unit_id: str
    T_source: float
    T_sink: float
    speed_ratio: float
    injected: str
    severity: float
    diagnosis: str
    confidence: float


def build_fleet(scenarios: SyntheticScenarios, size: int, seed: int) -> List[SimulatedUnit]:
    """Draw `size` units with a fixed seed, simulate each cycle and diagnose it."""
    rng = np.random.default_rng(seed)
    generator = scenarios.generator
    faults = [ft for ft in FaultType if ft != FaultType.NORMAL]
    units: List[SimulatedUnit] = []
    for index in range(size):
        healthy = rng.random() < HEALTHY_SHARE
        fault = FaultType.NORMAL if healthy else faults[int(rng.integers(len(faults)))]
        config = generator.fault_configs[fault]
        for _ in range(MAX_ATTEMPTS_PER_UNIT):
            T_source = float(rng.uniform(*generator.T_source_range))
            T_sink = float(rng.uniform(*generator.T_sink_range))
            speed = float(rng.uniform(*generator.speed_ratio_range))
            severity = 0.0 if healthy else float(rng.uniform(config.severity_min, config.severity_max))
            try:
                payload = scenarios.simulate_cycle(
                    T_source=T_source,
                    T_sink=T_sink,
                    speed_ratio=speed,
                    fault_type=fault.value,
                    severity=None if healthy else severity,
                )
            except Exception:
                continue
            if not all(math.isfinite(float(v)) for v in payload["features"].values()):
                continue
            diagnosis = payload["diagnosis"]
            units.append(
                SimulatedUnit(
                    unit_id=f"HP-{index + 1:03d}",
                    T_source=round(T_source, 1),
                    T_sink=round(T_sink, 1),
                    speed_ratio=round(speed, 2),
                    injected=fault.value,
                    severity=round(severity, 2),
                    diagnosis=str(diagnosis["label"]),
                    confidence=float(diagnosis["confidence"]),
                )
            )
            break
    return units


def _cached_fleet(request: Request, scenarios: SyntheticScenarios, size: int, seed: int):
    cache: Dict[Tuple[int, int], List[SimulatedUnit]] = getattr(request.app.state, "fleet_cache", None)
    if cache is None:
        cache = {}
        request.app.state.fleet_cache = cache
    key = (size, seed)
    if key not in cache:
        cache[key] = build_fleet(scenarios, size, seed)
    return cache[key]


def _optional_results(request: Request, settings: Settings = Depends(get_settings)) -> pd.DataFrame:
    try:
        return get_results(request, settings)
    except ArtifactMissing:
        return pd.DataFrame()


def triage(
    units: List[SimulatedUnit], results: pd.DataFrame, validated_only: bool, seed: int
) -> FleetResponse:
    """Apply the evidence policy to diagnosed units. Pure: no simulation here."""
    table = policy.evidence_by_class(results)
    rows: List[FleetUnit] = []
    held_back = 0
    for unit in units:
        evidence = policy.evidence_for(unit.diagnosis, table)
        action = policy.decide(unit.diagnosis, unit.confidence, evidence, validated_only)
        ungated = policy.decide(unit.diagnosis, unit.confidence, evidence, validated_only=False)
        if ungated == policy.DISPATCH and action != policy.DISPATCH:
            held_back += 1
        rows.append(
            FleetUnit(
                unit_id=unit.unit_id,
                T_source=unit.T_source,
                T_sink=unit.T_sink,
                speed_ratio=unit.speed_ratio,
                diagnosis=unit.diagnosis,
                confidence=unit.confidence,
                evidence=FleetEvidence(
                    status=evidence.status,
                    experiment=policy.EVIDENCE_EXPERIMENT,
                    protocol=policy.EVIDENCE_PROTOCOL,
                    f1=evidence.f1,
                    n=evidence.n,
                ),
                action=action,
                instruction=policy.instruction(action, unit.diagnosis),
                priority=policy.PRIORITY[action],
                ground_truth=unit.injected,
                ground_truth_severity=unit.severity,
            )
        )
    rows.sort(key=lambda row: (row.priority, -row.confidence, row.unit_id))
    counts = {action: sum(row.action == action for row in rows) for action in policy.PRIORITY}
    return FleetResponse(
        notice=NOTICE,
        seed=seed,
        policy=FleetPolicy(
            validated_only=validated_only,
            evidence_experiment=policy.EVIDENCE_EXPERIMENT,
            evidence_protocol=policy.EVIDENCE_PROTOCOL,
            evidence_f1_min=policy.EVIDENCE_F1_MIN,
            confidence_min=policy.CONFIDENCE_MIN,
        ),
        summary=FleetSummary(
            units=len(rows),
            dispatch=counts[policy.DISPATCH],
            engineering_review=counts[policy.ENGINEERING_REVIEW],
            monitor=counts[policy.MONITOR],
            no_action=counts[policy.NO_ACTION],
            held_back=held_back,
        ),
        units=rows,
    )


@router.get(
    "",
    response_model=FleetResponse,
    summary="Triage a simulated fleet: dispatch only on evidence-backed fault classes",
    operation_id="getFleet",
)
def fleet(
    request: Request,
    size: int = Query(24, ge=1, le=100),
    seed: int = Query(7, ge=0),
    scenarios: SyntheticScenarios = Depends(get_scenarios),
    results: pd.DataFrame = Depends(_optional_results),
    settings: Settings = Depends(get_settings),
) -> FleetResponse:
    units = _cached_fleet(request, scenarios, size, seed)
    return triage(units, results, settings.fleet_validated_only, seed)
