"""FastAPI inference service for heat-pump FDD."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from api.schemas import (
    ActivityResponse,
    BoxStats,
    CatalogResponse,
    Challenge,
    ChallengesResponse,
    ClassF1,
    ClassShare,
    ColumnStats,
    ConfusionMatrix,
    CopCurvePoint,
    CopMeasuredPoint,
    CopResponse,
    DatasetResponse,
    Diagnosis,
    DistributionResponse,
    Envelope,
    EnvelopeZone,
    FeatureImportance,
    FaultLabel,
    HealthResponse,
    LiveRequest,
    LiveResponse,
    LiveTracePoint,
    MatrixResponse,
    ModelCard,
    ModelComparisonRow,
    ModelsResponse,
    OverviewResponse,
    PhCompareResponse,
    PhCyclePoint,
    PhOverlay,
    PhResponse,
    PredictRequest,
    SaturationPoint,
    ScatterPoint,
    ScatterResponse,
    Scenario,
    SimulateRequest,
    SimulateResponse,
    StatsResponse,
    SweepPoint,
    SweepResponse,
    AshraeResponse,
    AshraeRow,
    AmbientHeatmapResponse,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.features import FEATURE_COLUMNS, SCENARIOS
from src.inference import FDDEngine
from src.studies.synthetic.scenarios import FAULT_PARAM_MAP, SyntheticScenarios
from src.thermo_lab import (
    ambient_heatmap,
    ashrae_table,
    condenser_sweep,
    cycle_state,
    evaporator_sweep,
    sweep_deltas,
)
from src.thermodynamic_viz import HAS_COOLPROP, ThermodynamicVisualizer

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
DATASET_PATH = OUTPUTS / "dataset_fdd.csv"
COMPARISON_PATH = OUTPUTS / "model_comparison.csv"
CONFUSION_PATH = OUTPUTS / "confusion_matrix.csv"
IMPORTANCE_PATH = OUTPUTS / "feature_importance.csv"

app = FastAPI(
    title="Heat Pump FDD API",
    description="Diagnose vapour-compression heat-pump faults from cycle features or simulated conditions.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = FDDEngine()
scenarios = SyntheticScenarios(engine)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=engine.metadata.get("model_name", engine.classifier.model_type),
        classes=engine.class_names,
    )


@app.post("/predict", response_model=Diagnosis)
def predict(body: PredictRequest) -> Diagnosis:
    try:
        return Diagnosis.model_validate(engine.predict(body.features.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest) -> SimulateResponse:
    payload = scenarios.simulate_cycle(
        T_source=body.T_source,
        T_sink=body.T_sink,
        speed_ratio=body.speed_ratio,
        fault_type=body.fault_type.value,
        severity=body.severity,
    )
    return SimulateResponse.model_validate(payload)


@app.post("/live", response_model=LiveResponse)
def live(body: LiveRequest) -> LiveResponse:
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


@lru_cache(maxsize=1)
def _class_counts() -> Dict[str, int]:
    if not DATASET_PATH.exists():
        return {name: 0 for name in engine.class_names}
    import pandas as pd

    df = pd.read_csv(DATASET_PATH)
    counts = df["fault_type"].value_counts().to_dict()
    return {name: int(counts.get(name, 0)) for name in engine.class_names}


@app.get("/api/stats", response_model=StatsResponse)
def api_stats(fault_type: FaultLabel = Query(FaultLabel.CONDENSER_FOULING)) -> StatsResponse:
    payload = scenarios.simulate_cycle(
        T_source=7.0,
        T_sink=40.0,
        speed_ratio=0.7,
        fault_type=fault_type.value,
    )
    cycle = payload["cycle"]
    diagnosis = payload["diagnosis"]
    return StatsResponse(
        fault_type=fault_type.value,
        label=diagnosis["label"],
        confidence=diagnosis["confidence"],
        probabilities=diagnosis["probabilities"],
        COP=cycle["COP"],
        P_cond=cycle["P_cond"],
        P_evap=cycle["P_evap"],
        T_discharge=cycle["T_discharge"],
        superheat=cycle["superheat"],
        subcooling=cycle["subcooling"],
        model=engine.metadata.get("model_name", engine.classifier.model_type),
    )


@app.get("/api/overview", response_model=OverviewResponse)
def api_overview() -> OverviewResponse:
    counts = _class_counts()
    total = sum(counts.values()) or 1
    return OverviewResponse(
        total=total,
        classes=[
            ClassShare(name=name, value=count, share=count / total)
            for name, count in counts.items()
        ],
        f1=engine.metadata.get("f1"),
        accuracy=engine.metadata.get("accuracy"),
    )


@app.get("/api/activity", response_model=ActivityResponse)
def api_activity(
    fault_type: FaultLabel = Query(FaultLabel.CONDENSER_FOULING),
    inject_at: int = Query(7, ge=1, le=40),
    n_points: int = Query(14, ge=10, le=60),
) -> ActivityResponse:
    trace = scenarios.live_trace(
        T_source=7.0,
        T_sink=40.0,
        speed_ratio=0.7,
        fault_type=fault_type.value,
        inject_at=inject_at,
        n_points=n_points,
        severity_final=0.40,
    )
    records = json.loads(trace.to_json(orient="records"))
    return ActivityResponse(
        fault_type=fault_type.value,
        inject_at=inject_at,
        trace=[LiveTracePoint.model_validate(row) for row in records],
    )


@app.get("/api/challenges", response_model=ChallengesResponse)
def api_challenges() -> ChallengesResponse:
    items = []
    for title, spec in SCENARIOS.items():
        payload = scenarios.simulate_cycle(
            T_source=7.0,
            T_sink=40.0,
            speed_ratio=0.7,
            fault_type=spec["fault_type"],
            **spec.get("params", {}),
        )
        predicted = payload["diagnosis"]["label"]
        expected = spec["fault_type"]
        matched = predicted == expected
        items.append(
            Challenge(
                id=expected,
                title=title,
                description=spec["description"],
                injected=expected,
                predicted=predicted,
                confidence=payload["diagnosis"]["confidence"],
                status="Complete" if matched else "On Going",
                progress=int(round(payload["diagnosis"]["confidence"] * 100)),
            )
        )
    return ChallengesResponse(challenges=items)


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing {path.name}. Run main_analysis.py first.")
    return pd.read_csv(path, **kwargs)


@lru_cache(maxsize=1)
def _dataset() -> pd.DataFrame:
    return _read_csv(DATASET_PATH)


@app.get("/api/catalog", response_model=CatalogResponse)
def api_catalog() -> CatalogResponse:
    return CatalogResponse(
        classes=engine.class_names,
        features=engine.feature_names,
        faults=list(FAULT_PARAM_MAP.keys()),
        scenarios=[
            Scenario(
                title=title,
                fault_type=spec["fault_type"],
                params=spec.get("params", {}),
                description=spec["description"],
            )
            for title, spec in SCENARIOS.items()
        ],
        model=ModelCard(
            name=engine.metadata.get("model_name", engine.classifier.model_type),
            accuracy=engine.metadata.get("accuracy"),
            precision=engine.metadata.get("precision"),
            recall=engine.metadata.get("recall"),
            f1=engine.metadata.get("f1"),
            f1_per_class=engine.metadata.get("f1_per_class") or {},
            n_samples=engine.metadata.get("n_samples"),
            n_features=engine.metadata.get("n_features"),
            calibrated=bool(engine.metadata.get("calibrated", True)),
            coolprop=bool(engine.metadata.get("coolprop", HAS_COOLPROP)),
        ),
    )


@app.get("/api/models", response_model=ModelsResponse)
def api_models() -> ModelsResponse:
    comparison = _read_csv(COMPARISON_PATH)
    confusion = _read_csv(CONFUSION_PATH, index_col=0)
    importance = _read_csv(IMPORTANCE_PATH)
    labels = [str(c) for c in confusion.columns]
    matrix = (
        confusion.loc[labels, labels].astype(float).values.tolist()
        if set(labels).issubset(set(map(str, confusion.index)))
        else confusion.astype(float).values.tolist()
    )
    return ModelsResponse(
        metadata=engine.metadata,
        comparison=[
            ModelComparisonRow.model_validate(row) for row in comparison.to_dict(orient="records")
        ],
        confusion=ConfusionMatrix(labels=labels, matrix=matrix),
        importance=[
            FeatureImportance.model_validate(row)
            for row in importance.head(15).to_dict(orient="records")
        ],
        f1_per_class=[
            ClassF1(name=name, f1=float(score))
            for name, score in (engine.metadata.get("f1_per_class") or {}).items()
        ],
    )


@app.get("/api/dataset", response_model=DatasetResponse)
def api_dataset() -> DatasetResponse:
    df = _dataset()
    counts = df["fault_type"].value_counts().to_dict() if "fault_type" in df.columns else {}
    total = int(len(df))
    numeric = df.select_dtypes(include="number")
    describe = {
        col: ColumnStats(
            mean=float(numeric[col].mean()),
            std=float(numeric[col].std()),
            min=float(numeric[col].min()),
            max=float(numeric[col].max()),
        )
        for col in ["COP", "P_cond", "P_evap", "T_discharge", "superheat", "subcooling"]
        if col in numeric.columns
    }
    return DatasetResponse(
        n_samples=total,
        n_classes=int(df["fault_type"].nunique()) if "fault_type" in df.columns else 0,
        normal_share=float(counts.get("Normal", 0) / total) if total else 0.0,
        counts={name: int(counts.get(name, 0)) for name in engine.class_names},
        describe=describe,
        columns=[c for c in FEATURE_COLUMNS if c in df.columns],
    )


@app.get("/api/explore/distribution", response_model=DistributionResponse)
def api_distribution(feature: str = Query("superheat")) -> DistributionResponse:
    df = _dataset()
    if feature not in df.columns:
        raise HTTPException(status_code=422, detail=f"Unknown feature: {feature}")
    boxes = []
    for name, group in df.groupby("fault_type"):
        values = group[feature].dropna().astype(float)
        if values.empty:
            continue
        boxes.append(
            BoxStats(
                name=str(name),
                min=float(values.min()),
                q1=float(values.quantile(0.25)),
                median=float(values.median()),
                q3=float(values.quantile(0.75)),
                max=float(values.max()),
                mean=float(values.mean()),
            )
        )
    return DistributionResponse(feature=feature, boxes=boxes)


@app.get("/api/explore/scatter", response_model=ScatterResponse)
def api_scatter(
    x: str = Query("delta_T_evap"),
    y: str = Query("delta_T_cond"),
    limit: int = Query(720, ge=60, le=2000),
) -> ScatterResponse:
    df = _dataset()
    for col in (x, y, "fault_type"):
        if col not in df.columns:
            raise HTTPException(status_code=422, detail=f"Unknown column: {col}")
    per_class = max(limit // max(df["fault_type"].nunique(), 1), 20)
    parts: List[pd.DataFrame] = []
    for _, group in df.groupby("fault_type"):
        parts.append(group.sample(n=min(per_class, len(group)), random_state=0))
    sample = pd.concat(parts, ignore_index=True)
    return ScatterResponse(
        x=x,
        y=y,
        points=[
            ScatterPoint(x=float(row[x]), y=float(row[y]), fault_type=str(row["fault_type"]))
            for row in sample[[x, y, "fault_type"]].to_dict(orient="records")
        ],
    )


@app.get("/api/advanced", response_model=MatrixResponse)
def api_advanced() -> MatrixResponse:
    df = _dataset()
    cols = [
        c
        for c in [
            "COP",
            "P_cond",
            "P_evap",
            "superheat",
            "subcooling",
            "T_discharge",
            "d_COP",
            "d_superheat",
            "d_subcooling",
            "delta_T_cond",
            "delta_T_evap",
            "W_comp",
        ]
        if c in df.columns
    ]
    corr = df[cols].corr().fillna(0.0)
    return MatrixResponse(labels=cols, matrix=corr.astype(float).values.tolist())


@lru_cache(maxsize=1)
def _saturation_curve() -> tuple:
    viz = ThermodynamicVisualizer()
    temps = np.linspace(-40, 70, 80)
    return tuple(
        SaturationPoint(
            T=float(T),
            P=float(viz._sat_pressure(float(T))),
            h_liq=float(viz._enthalpy_liquid(float(T))),
            h_vap=float(viz._enthalpy_vapor(float(T))),
        )
        for T in temps
    )


def _ph_overlay(
    t_evap: float,
    t_cond: float,
    superheat: float,
    subcooling: float,
    eta_is: float = 0.75,
) -> PhOverlay:
    state = cycle_state(t_evap, t_cond, superheat, subcooling, eta_is)
    return PhOverlay(
        T_evap=state["T_evap"],
        T_cond=state["T_cond"],
        P_evap=state["P_evap"],
        P_cond=state["P_cond"],
        COP=state["COP"],
        cycle=[
            PhCyclePoint(name="1 suction", h=state["h1"], P=state["P_evap"]),
            PhCyclePoint(name="2 discharge", h=state["h2"], P=state["P_cond"]),
            PhCyclePoint(name="3 liquid", h=state["h3"], P=state["P_cond"]),
            PhCyclePoint(name="4 two-phase", h=state["h4"], P=state["P_evap"]),
            PhCyclePoint(name="1 suction", h=state["h1"], P=state["P_evap"]),
        ],
    )


@app.get("/api/thermo/ph", response_model=PhResponse)
def api_thermo_ph(
    T_evap: float = Query(5.0),
    T_cond: float = Query(45.0),
    superheat: float = Query(6.0, ge=0.0, le=20.0),
    subcooling: float = Query(5.0, ge=0.0, le=20.0),
    eta_is: float = Query(0.75, ge=0.4, le=1.0),
) -> PhResponse:
    overlay = _ph_overlay(T_evap, T_cond, superheat, subcooling, eta_is)
    return PhResponse(
        coolprop=HAS_COOLPROP,
        P_evap=overlay.P_evap,
        P_cond=overlay.P_cond,
        COP=overlay.COP,
        saturation=list(_saturation_curve()),
        cycle=overlay.cycle,
        envelope=Envelope(
            normal=EnvelopeZone(T_evap=[-20, 20], T_cond=[25, 65]),
            extended=EnvelopeZone(T_evap=[-30, 25], T_cond=[20, 70]),
        ),
    )


@app.get("/api/thermo/ph/compare", response_model=PhCompareResponse)
def api_thermo_ph_compare(
    T_evap: float = Query(0.0, ge=-10.0, le=10.0),
    T_cond: float = Query(45.0, ge=35.0, le=55.0),
    superheat: float = Query(8.0, ge=2.0, le=15.0),
    subcooling: float = Query(5.0, ge=2.0, le=12.0),
    load_factor: float = Query(50.0, ge=30.0, le=100.0),
    t_source: float = Query(-10.0, ge=-15.0, le=15.0),
    scenario: Literal["nominal", "condenser", "evaporator", "all"] = Query("all"),
) -> PhCompareResponse:
    nominal = _ph_overlay(T_evap, T_cond, superheat, subcooling)
    condenser = None
    evaporator = None
    if scenario in ("condenser", "all"):
        t_cond_load = T_cond + (100.0 - load_factor) / 100.0 * 15.0
        condenser = _ph_overlay(T_evap, t_cond_load, superheat, subcooling)
    if scenario in ("evaporator", "all"):
        evaporator = _ph_overlay(t_source - 5.0, T_cond, superheat, subcooling)
    return PhCompareResponse(
        coolprop=HAS_COOLPROP,
        scenario=scenario,
        saturation=list(_saturation_curve()),
        nominal=nominal,
        condenser=condenser,
        evaporator=evaporator,
    )


@app.get("/api/thermo/cop", response_model=CopResponse)
def api_thermo_cop() -> CopResponse:
    df = _dataset()
    T_amb = np.linspace(-10, 45, 40)
    t_source = 20.0
    carnot = np.clip((t_source + 273.15) / (T_amb - t_source + 0.1), 0, 15)
    real = np.clip(carnot * 0.45, 0, 6)
    curves = [
        CopCurvePoint(T_amb=float(t), carnot=float(c), estimated=float(r))
        for t, c, r in zip(T_amb, carnot, real)
    ]
    measured: List[CopMeasuredPoint] = []
    if {"T_ambient", "COP", "fault_type"}.issubset(df.columns):
        sample = df[df["fault_type"] == "Normal"].sample(
            n=min(400, int((df["fault_type"] == "Normal").sum())),
            random_state=0,
        )
        measured = [
            CopMeasuredPoint(T_amb=float(row["T_ambient"]), COP=float(row["COP"]))
            for row in sample.to_dict(orient="records")
        ]
    return CopResponse(curves=curves, measured=measured)


@app.get("/api/thermo/sweep/condenser", response_model=SweepResponse)
def api_sweep_condenser(
    T_evap: float = Query(0.0, ge=-10.0, le=10.0),
    load_min: float = Query(30.0, ge=20.0, le=90.0),
    load_max: float = Query(100.0, ge=40.0, le=100.0),
) -> SweepResponse:
    lo, hi = min(load_min, load_max), max(load_min, load_max)
    points = condenser_sweep(t_evap=T_evap, load_min=lo, load_max=hi)
    return SweepResponse(
        kind="condenser",
        coolprop=HAS_COOLPROP,
        points=[SweepPoint.model_validate(row) for row in points],
        deltas=sweep_deltas(points, ["COP", "W_comp", "tau", "T_dis"]),
        headline="Main impact: compressor power up",
    )


@app.get("/api/thermo/sweep/evaporator", response_model=SweepResponse)
def api_sweep_evaporator(
    T_cond: float = Query(45.0, ge=35.0, le=55.0),
    source_min: float = Query(-15.0, ge=-20.0, le=5.0),
    source_max: float = Query(7.0, ge=-5.0, le=15.0),
) -> SweepResponse:
    lo, hi = min(source_min, source_max), max(source_min, source_max)
    points = evaporator_sweep(t_cond=T_cond, source_min=lo, source_max=hi)
    return SweepResponse(
        kind="evaporator",
        coolprop=HAS_COOLPROP,
        points=[SweepPoint.model_validate(row) for row in points],
        deltas=sweep_deltas(points, ["COP", "P_evap", "tau", "Q_evap"]),
        headline="Main impact: heating capacity down",
    )


@app.get("/api/thermo/ashrae", response_model=AshraeResponse)
def api_thermo_ashrae() -> AshraeResponse:
    return AshraeResponse(
        coolprop=HAS_COOLPROP,
        rows=[AshraeRow.model_validate(row) for row in ashrae_table()],
    )


@app.get("/api/advanced/ambient", response_model=AmbientHeatmapResponse)
def api_ambient_heatmap() -> AmbientHeatmapResponse:
    df = _dataset()
    if "T_ambient" not in df.columns or "fault_type" not in df.columns:
        raise HTTPException(status_code=404, detail="Dataset missing T_ambient or fault_type")
    x_labels, y_labels, matrix = ambient_heatmap(df)
    return AmbientHeatmapResponse(x_labels=x_labels, y_labels=y_labels, matrix=matrix)
