"""FastAPI inference service for heat-pump FDD."""

import json
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.inference import FDDEngine

app = FastAPI(
    title="Heat Pump FDD API",
    description="Diagnose vapour-compression heat-pump faults from cycle features or simulated conditions.",
    version="1.0.0",
)
engine = FDDEngine()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


class PredictRequest(BaseModel):
    features: Dict[str, float]


class SimulateRequest(BaseModel):
    T_source: float = Field(7.0, description="Evaporator source temperature °C")
    T_sink: float = Field(40.0, description="Condenser sink temperature °C")
    speed_ratio: float = Field(0.7, ge=0.3, le=1.0)
    fault_type: str = "Normal"
    severity: Optional[float] = Field(None, ge=0.0, le=1.0)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": engine.metadata.get("model_name", engine.classifier.model_type),
        "classes": engine.class_names,
    }


@app.post("/predict")
def predict(body: PredictRequest):
    try:
        return engine.predict(body.features)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/simulate")
def simulate(body: SimulateRequest):
    return engine.simulate_cycle(
        T_source=body.T_source,
        T_sink=body.T_sink,
        speed_ratio=body.speed_ratio,
        fault_type=body.fault_type,
        severity=body.severity,
    )


class LiveRequest(BaseModel):
    T_source: float = 7.0
    T_sink: float = 40.0
    speed_ratio: float = Field(0.7, ge=0.3, le=1.0)
    fault_type: str = "Condenser_Fouling"
    inject_at: int = Field(25, ge=1, le=80)
    n_points: int = Field(60, ge=10, le=120)
    severity_final: float = Field(0.40, ge=0.0, le=1.0)


@app.post("/live")
def live(body: LiveRequest):
    trace = engine.live_trace(
        T_source=body.T_source,
        T_sink=body.T_sink,
        speed_ratio=body.speed_ratio,
        fault_type=body.fault_type,
        inject_at=body.inject_at,
        n_points=body.n_points,
        severity_final=body.severity_final,
    )
    return {"trace": json.loads(trace.to_json(orient="records"))}
