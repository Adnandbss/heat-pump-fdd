"""Routes that feed the React dashboard views."""

from __future__ import annotations

import json
import math
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, Depends, Query

from api.deps import (
    get_class_counts,
    get_dataset,
    get_engine,
    get_scenarios,
    get_settings,
    read_artefact_csv,
)
from api.errors import ArtifactMissing, UnknownFeature
from api.schemas.dashboard import (
    ActivityResponse,
    AmbientHeatmapResponse,
    BoxStats,
    CatalogResponse,
    Challenge,
    ChallengesResponse,
    ClassF1,
    ClassShare,
    ColumnStats,
    ConfusionMatrix,
    DatasetResponse,
    DistributionResponse,
    FeatureImportance,
    MatrixResponse,
    ModelCard,
    ModelComparisonRow,
    ModelsResponse,
    OverviewResponse,
    ScatterPoint,
    ScatterResponse,
    Scenario,
    StatsResponse,
)
from api.schemas.inference import FaultLabel, LiveTracePoint
from api.settings import Settings
from src.fdd.features import FEATURE_COLUMNS
from src.fdd.inference import FDDEngine
from src.physics.thermo_lab import ambient_heatmap
from src.physics.thermodynamic_viz import HAS_COOLPROP
from src.studies.synthetic.scenarios import SyntheticScenarios
from src.studies.synthetic.taxonomy import FAULT_PARAM_MAP, SCENARIOS

router = APIRouter(tags=["dashboard"])


@router.get(
    "/api/stats",
    response_model=StatsResponse,
    summary="One simulated point for the stats cards",
    operation_id="getStats",
)
def api_stats(
    fault_type: FaultLabel = Query(FaultLabel.CONDENSER_FOULING),
    engine: FDDEngine = Depends(get_engine),
    scenarios: SyntheticScenarios = Depends(get_scenarios),
) -> StatsResponse:
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


@router.get(
    "/api/overview",
    response_model=OverviewResponse,
    summary="Class counts and headline metrics",
    operation_id="getOverview",
)
def api_overview(
    engine: FDDEngine = Depends(get_engine),
    counts: Dict[str, int] = Depends(get_class_counts),
) -> OverviewResponse:
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


@router.get(
    "/api/activity",
    response_model=ActivityResponse,
    summary="Short live trace for the activity strip",
    operation_id="getActivity",
)
def api_activity(
    fault_type: FaultLabel = Query(FaultLabel.CONDENSER_FOULING),
    inject_at: int = Query(7, ge=1, le=40),
    n_points: int = Query(14, ge=10, le=60),
    scenarios: SyntheticScenarios = Depends(get_scenarios),
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


@router.get(
    "/api/challenges",
    response_model=ChallengesResponse,
    summary="Named demo scenarios and whether the model matches",
    operation_id="getChallenges",
)
def api_challenges(
    scenarios: SyntheticScenarios = Depends(get_scenarios),
) -> ChallengesResponse:
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


@router.get(
    "/api/catalog",
    response_model=CatalogResponse,
    summary="Classes, features, scenarios, and model card",
    operation_id="getCatalog",
)
def api_catalog(engine: FDDEngine = Depends(get_engine)) -> CatalogResponse:
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


@router.get(
    "/api/models",
    response_model=ModelsResponse,
    summary="Comparison table, confusion matrix, feature importance",
    operation_id="getModels",
)
def api_models(
    engine: FDDEngine = Depends(get_engine),
    settings: Settings = Depends(get_settings),
) -> ModelsResponse:
    comparison = read_artefact_csv(settings.comparison_path)
    confusion = read_artefact_csv(settings.confusion_path, index_col=0)
    importance = read_artefact_csv(settings.importance_path)
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


@router.get(
    "/api/dataset",
    response_model=DatasetResponse,
    summary="Dataset size, class mix, and column summaries",
    operation_id="getDataset",
)
def api_dataset(
    engine: FDDEngine = Depends(get_engine),
    df: pd.DataFrame = Depends(get_dataset),
) -> DatasetResponse:
    counts = df["fault_type"].value_counts().to_dict() if "fault_type" in df.columns else {}
    total = int(len(df))
    numeric = df.select_dtypes(include="number")

    def _finite(value: float) -> float:
        number = float(value)
        return 0.0 if math.isnan(number) or math.isinf(number) else number

    describe = {
        col: ColumnStats(
            mean=_finite(numeric[col].mean()),
            std=_finite(numeric[col].std()),
            min=_finite(numeric[col].min()),
            max=_finite(numeric[col].max()),
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


@router.get(
    "/api/explore/distribution",
    response_model=DistributionResponse,
    summary="Per-class box stats for one feature",
    operation_id="getDistribution",
)
def api_distribution(
    feature: str = Query("superheat"),
    df: pd.DataFrame = Depends(get_dataset),
) -> DistributionResponse:
    if feature not in df.columns:
        raise UnknownFeature(feature)
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


@router.get(
    "/api/explore/scatter",
    response_model=ScatterResponse,
    summary="Stratified scatter sample of two columns",
    operation_id="getScatter",
)
def api_scatter(
    x: str = Query("delta_T_evap"),
    y: str = Query("delta_T_cond"),
    limit: int = Query(720, ge=60, le=2000),
    df: pd.DataFrame = Depends(get_dataset),
) -> ScatterResponse:
    for col in (x, y, "fault_type"):
        if col not in df.columns:
            raise UnknownFeature(col, kind="column")
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


@router.get(
    "/api/advanced",
    response_model=MatrixResponse,
    summary="Correlation matrix of cycle features",
    operation_id="getCorrelationMatrix",
)
def api_advanced(df: pd.DataFrame = Depends(get_dataset)) -> MatrixResponse:
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


@router.get(
    "/api/advanced/ambient",
    response_model=AmbientHeatmapResponse,
    summary="Fault counts by ambient-temperature bin",
    operation_id="getAmbientHeatmap",
)
def api_ambient_heatmap(df: pd.DataFrame = Depends(get_dataset)) -> AmbientHeatmapResponse:
    if "T_ambient" not in df.columns or "fault_type" not in df.columns:
        raise ArtifactMissing("dataset.csv", "Dataset missing T_ambient or fault_type")
    x_labels, y_labels, matrix = ambient_heatmap(df)
    return AmbientHeatmapResponse(x_labels=x_labels, y_labels=y_labels, matrix=matrix)
