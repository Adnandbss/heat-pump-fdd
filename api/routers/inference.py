"""Diagnosis routes: health, predict, simulate, live."""

from __future__ import annotations

import json

import pandas as pd
from fastapi import APIRouter, Depends, Request

from api.deps import get_engine, get_results, get_scenarios, get_settings
from api.errors import ArtifactMissing, InvalidFeatureVector
from api.fleet_policy import EVIDENCE_EXPERIMENT, EVIDENCE_PROTOCOL, service_decision
from api.schemas.inference import (
    Diagnosis,
    HealthResponse,
    LiveRequest,
    LiveResponse,
    LiveTracePoint,
    PredictRequest,
    ServiceDecision,
    SimulateRequest,
    SimulateResponse,
)
from api.settings import Settings
from src.fdd.inference import FDDEngine
from src.studies.synthetic.scenarios import SyntheticScenarios

router = APIRouter(tags=["inference"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Loaded model and class list",
    operation_id="getHealth",
)
def health(engine: FDDEngine = Depends(get_engine)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=engine.metadata.get("model_name", engine.classifier.model_type),
        classes=engine.class_names,
    )


@router.post(
    "/predict",
    response_model=Diagnosis,
    summary="Diagnose a 23-d cycle feature vector",
    operation_id="predictFault",
)
def predict(
    body: PredictRequest,
    engine: FDDEngine = Depends(get_engine),
) -> Diagnosis:
    try:
        return Diagnosis.model_validate(engine.predict(body.features.model_dump()))
    except ValueError as exc:
        raise InvalidFeatureVector(str(exc)) from exc


def _results_or_empty(request: Request, settings: Settings = Depends(get_settings)) -> pd.DataFrame:
    try:
        return get_results(request, settings)
    except ArtifactMissing:
        return pd.DataFrame()


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    summary="Simulate a cycle and diagnose it",
    operation_id="simulateCycle",
)
def simulate(
    body: SimulateRequest,
    scenarios: SyntheticScenarios = Depends(get_scenarios),
    results: pd.DataFrame = Depends(_results_or_empty),
    settings: Settings = Depends(get_settings),
) -> SimulateResponse:
    payload = scenarios.simulate_cycle(
        T_source=body.T_source,
        T_sink=body.T_sink,
        speed_ratio=body.speed_ratio,
        fault_type=body.fault_type.value,
        severity=body.severity,
    )
    diagnosis = payload["diagnosis"]
    action, text, evidence = service_decision(
        diagnosis["label"], diagnosis["confidence"], results, settings.fleet_validated_only
    )
    payload["service_decision"] = ServiceDecision(
        action=action,
        instruction=text,
        evidence_status=evidence.status,
        evidence_experiment=EVIDENCE_EXPERIMENT,
        evidence_protocol=EVIDENCE_PROTOCOL,
        evidence_f1=evidence.f1,
    )
    return SimulateResponse.model_validate(payload)


@router.post(
    "/live",
    response_model=LiveResponse,
    summary="Time series with a fault injected mid-trace",
    operation_id="getLiveTrace",
)
def live(
    body: LiveRequest,
    scenarios: SyntheticScenarios = Depends(get_scenarios),
) -> LiveResponse:
    trace = scenarios.live_trace(
        T_source=body.T_source,
        T_sink=body.T_sink,
        speed_ratio=body.speed_ratio,
        fault_type=body.fault_type.value,
        inject_at=body.inject_at,
        n_points=body.n_points,
        severity_final=body.severity_final,
    )
    records = json.loads(trace.to_json(orient="records"))
    return LiveResponse(trace=[LiveTracePoint.model_validate(row) for row in records])
