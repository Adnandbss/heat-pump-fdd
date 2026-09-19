"""Logged experiment results. No classifier load — Evidence works without the joblib."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, Query

from api.deps import get_results, get_settings
from api.errors import ArtifactMissing
from api.schemas.evidence import (
    EvidenceConfusion,
    EvidenceLadder,
    EvidencePerClass,
    EvidenceProtocols,
    EvidenceReferences,
    EvidenceRuns,
    EvidenceSummary,
    LadderRung,
    PerClassScores,
    ProtocolRef,
    ProtocolSlopePoint,
    ReferencePoint,
    RunRow,
    SummaryCard,
)
from api.settings import ROOT, Settings

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

_REF_RE = re.compile(
    r"^(?P<family>.+)-(?P<conditioning>TT|TTdew)-dmin(?P<dmin>[0-9.]+)$"
)
_KNN_FACET = re.compile(r"^(knn-k\d+)-median-unif$")

# Display order for figure 4. None = not measurable on that regime (hole, not zero).
_CLASS_ALIGN: List[Tuple[str, Optional[str], Optional[str]]] = [
    ("Undercharge", "Refrigerant_Undercharge", "Undercharge"),
    ("Overcharge", "Refrigerant_Overcharge", "Overcharge"),
    ("No_Fault", "Normal", "No_Fault"),
    ("Evap_Airflow", None, "Evap_Airflow"),
    ("Cond_Blockage", "Condenser_Fouling", "Cond_Blockage"),
    ("LiquidLine", None, "LiquidLine"),
]

_LADDER: List[Dict[str, Any]] = [
    {
        "cause": "d_COP fuitait le label",
        "band": "simulator",
        "lookup": {
            "experiment": "X0",
            "protocol": "leaked-dCOP",
            "reference": "simulated",
            "features": "24-col",
            "model": "random-forest",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "6 classes, dont une fantôme non modélisée",
        "band": "simulator",
        "lookup": {
            "experiment": "X0",
            "protocol": "holdout-test-6class",
            "reference": "simulated",
            "features": "24-col",
            "model": "random-forest",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "7 classes, hold-out honnête",
        "band": "simulator",
        "lookup": {
            "experiment": "X0",
            "protocol": "holdout-test",
            "reference": "simulated",
            "features": "23-col",
            "model": "random-forest",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "LOMO, résidus, référence sur la machine cible",
        "band": "nist",
        "lookup": {
            "experiment": "X0b",
            "protocol": "LOMO",
            "reference": "target-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "sim2real : entraîné sur le simulateur, testé sur le réel",
        "band": "nist",
        "lookup": {
            "experiment": "X5",
            "protocol": "sim2real",
            "reference": "measured-knn5",
            "features": "residuals",
            "model": "random-forest",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "LOMO, référence transférée d'une autre machine",
        "band": "nist",
        "lookup": {
            "experiment": "X1",
            "protocol": "LOMO",
            "reference": "training-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
    {
        "cause": "classe majoritaire",
        "band": "nist",
        "majority": True,
        "lookup": {
            "experiment": "X0b",
            "protocol": "majority-class",
            "reference": "none",
            "features": "",
            "model": "baseline",
            "label": "__global__",
            "metric": "accuracy",
        },
    },
]


def _nan_to_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _match(df: pd.DataFrame, lookup: Dict[str, str]) -> Optional[pd.Series]:
    work = df
    for key, expected in lookup.items():
        if key not in work.columns:
            return None
        series = work[key].fillna("").astype(str)
        work = work[series == str(expected)]
    if work.empty:
        return None
    return work.iloc[0]


def _protocol(row: pd.Series) -> ProtocolRef:
    return ProtocolRef(
        experiment=str(row.get("experiment", "")),
        protocol=str(row.get("protocol", "")),
        reference=str(row.get("reference", "")),
        features=str(row.get("features", "") or ""),
        model=str(row.get("model", "") or ""),
    )


def _facet(family: str) -> str:
    knn = _KNN_FACET.match(family)
    if knn:
        return knn.group(1)
    return family


def _int_or_none(value: Any) -> Optional[int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


@router.get(
    "/summary",
    response_model=EvidenceSummary,
    summary="Headline cards from the results log",
    operation_id="getEvidenceSummary",
)
def evidence_summary(df: pd.DataFrame = Depends(get_results)) -> EvidenceSummary:
    experiments = sorted({str(x) for x in df["experiment"].dropna().unique()})
    protocols = sorted({str(x) for x in df["protocol"].dropna().unique()})
    headline = _match(
        df,
        {
            "experiment": "X0",
            "protocol": "holdout-test",
            "reference": "simulated",
            "features": "23-col",
            "model": "random-forest",
            "label": "__global__",
            "metric": "accuracy",
        },
    )
    headline_value = _nan_to_none(headline["value"]) if headline is not None else None
    headline_protocol = _protocol(headline) if headline is not None else None
    cards = [
        SummaryCard(key="experiments", label="Experiments", value=str(len(experiments))),
        SummaryCard(key="measurements", label="Measurements", value=str(len(df))),
        SummaryCard(key="protocols", label="Protocols", value=str(len(protocols))),
        SummaryCard(
            key="headline",
            label="Headline accuracy",
            value="" if headline_value is None else f"{headline_value * 100:.1f}",
            protocol=headline_protocol,
        ),
    ]
    return EvidenceSummary(
        n_experiments=len(experiments),
        n_measurements=int(len(df)),
        n_protocols=len(protocols),
        headline_value=headline_value,
        headline_percent=None if headline_value is None else headline_value * 100.0,
        headline_protocol=headline_protocol,
        cards=cards,
    )


@router.get(
    "/ladder",
    response_model=EvidenceLadder,
    summary="Truth ladder: each rung is one logged accuracy",
    operation_id="getEvidenceLadder",
)
def evidence_ladder(df: pd.DataFrame = Depends(get_results)) -> EvidenceLadder:
    rungs: List[LadderRung] = []
    majority: Optional[float] = None
    for spec in _LADDER:
        row = _match(df, spec["lookup"])
        if row is None:
            continue
        value = _nan_to_none(row["value"])
        if value is None:
            continue
        if spec.get("majority"):
            majority = value
        rungs.append(
            LadderRung(
                value=value,
                percent=value * 100.0,
                cause=spec["cause"],
                band=spec["band"],
                majority=bool(spec.get("majority")),
                protocol=_protocol(row),
            )
        )
    return EvidenceLadder(rungs=rungs, majority=majority)


@router.get(
    "/protocols",
    response_model=EvidenceProtocols,
    summary="X0b: feature sets against random-CV vs LOMO",
    operation_id="getEvidenceProtocols",
)
def evidence_protocols(df: pd.DataFrame = Depends(get_results)) -> EvidenceProtocols:
    wanted = ["raw", "residuals", "raw+residuals", "residuals+conditions"]
    series: List[ProtocolSlopePoint] = []
    for features in wanted:
        cv = _match(
            df,
            {
                "experiment": "X0b",
                "protocol": "random-cv",
                "reference": "target-machine",
                "features": features,
                "model": "gradient-boosting",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        lomo = _match(
            df,
            {
                "experiment": "X0b",
                "protocol": "LOMO",
                "reference": "target-machine",
                "features": features,
                "model": "gradient-boosting",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        if cv is None and lomo is None:
            continue
        series.append(
            ProtocolSlopePoint(
                features=features,
                random_cv=_nan_to_none(cv["value"]) if cv is not None else None,
                lomo=_nan_to_none(lomo["value"]) if lomo is not None else None,
                protocol_cv=_protocol(cv) if cv is not None else None,
                protocol_lomo=_protocol(lomo) if lomo is not None else None,
            )
        )
    return EvidenceProtocols(series=series)


@router.get(
    "/references",
    response_model=EvidenceReferences,
    summary="X3 healthy-reference benchmark grid",
    operation_id="getEvidenceReferences",
)
def evidence_references(df: pd.DataFrame = Depends(get_results)) -> EvidenceReferences:
    subset = df[
        (df["experiment"] == "X3")
        & (df["protocol"] == "LOMO")
        & (df["metric"] == "accuracy")
        & (df["label"].fillna("__global__").astype(str) == "__global__")
    ]
    points: List[ReferencePoint] = []
    for _, row in subset.iterrows():
        parsed = _REF_RE.match(str(row.get("reference", "")))
        if not parsed:
            continue
        accuracy = _nan_to_none(row["value"])
        if accuracy is None:
            continue
        family = parsed.group("family")
        points.append(
            ReferencePoint(
                family=family,
                facet=_facet(family),
                conditioning=parsed.group("conditioning"),
                dmin=float(parsed.group("dmin")),
                accuracy=accuracy,
                protocol=_protocol(row),
            )
        )
    majority_row = _match(
        df,
        {
            "experiment": "X0b",
            "protocol": "majority-class",
            "reference": "none",
            "features": "",
            "model": "baseline",
            "label": "__global__",
            "metric": "accuracy",
        },
    )
    majority = _nan_to_none(majority_row["value"]) if majority_row is not None else None

    def _ann(family: str, conditioning: str, dmin: float) -> Optional[ReferencePoint]:
        for point in points:
            if (
                point.family == family
                and point.conditioning == conditioning
                and abs(point.dmin - dmin) < 1e-9
            ):
                return point
        return None

    return EvidenceReferences(
        points=points,
        majority=majority,
        annotation_dmin0=_ann("knn-k5-median-unif", "TT", 0.0),
        annotation_dmin05=_ann("knn-k5-median-unif", "TT", 0.5),
    )


@router.get(
    "/per-class",
    response_model=EvidencePerClass,
    summary="Per-class F1 on simulator vs NIST target vs transferred",
    operation_id="getEvidencePerClass",
)
def evidence_per_class(df: pd.DataFrame = Depends(get_results)) -> EvidencePerClass:
    def f1(lookup: Dict[str, str]) -> Optional[float]:
        row = _match(df, lookup)
        if row is None:
            return None
        return _nan_to_none(row["value"])

    rows: List[PerClassScores] = []
    for display, sim_label, nist_label in _CLASS_ALIGN:
        simulated = None
        if sim_label:
            simulated = f1(
                {
                    "experiment": "X5",
                    "protocol": "holdout-test",
                    "reference": "simulated",
                    "features": "residuals",
                    "model": "random-forest",
                    "label": sim_label,
                    "metric": "f1",
                }
            )
        target = None
        transferred = None
        if nist_label:
            target = f1(
                {
                    "experiment": "X1",
                    "protocol": "LOMO",
                    "reference": "target-machine",
                    "features": "residuals",
                    "model": "gradient-boosting",
                    "label": nist_label,
                    "metric": "f1",
                }
            )
            transferred = f1(
                {
                    "experiment": "X1",
                    "protocol": "LOMO",
                    "reference": "training-machine",
                    "features": "residuals",
                    "model": "gradient-boosting",
                    "label": nist_label,
                    "metric": "f1",
                }
            )
        rows.append(
            PerClassScores(
                display=display,
                simulated=simulated,
                target=target,
                transferred=transferred,
            )
        )
    rows.sort(key=lambda item: item.target if item.target is not None else -1.0, reverse=True)
    protocols = {
        "simulated": ProtocolRef(
            experiment="X5",
            protocol="holdout-test",
            reference="simulated",
            features="residuals",
            model="random-forest",
        ),
        "target": ProtocolRef(
            experiment="X1",
            protocol="LOMO",
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
        ),
        "transferred": ProtocolRef(
            experiment="X1",
            protocol="LOMO",
            reference="training-machine",
            features="residuals",
            model="gradient-boosting",
        ),
    }
    return EvidencePerClass(
        rows=rows,
        notes=[
            "Overcharge rises when the healthy reference is transferred.",
            "LiquidLine is never detected. The simulator does not model it.",
        ],
        protocols=protocols,
    )


@router.get(
    "/runs",
    response_model=EvidenceRuns,
    summary="Paginated results.csv rows",
    operation_id="getEvidenceRuns",
)
def evidence_runs(
    df: pd.DataFrame = Depends(get_results),
    experiment: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> EvidenceRuns:
    work = df.copy()
    experiments = sorted({str(x) for x in df["experiment"].dropna().unique()})
    protocols = sorted({str(x) for x in df["protocol"].dropna().unique()})
    models = sorted({str(x) for x in df["model"].fillna("").astype(str).unique() if str(x)})
    labels = sorted({str(x) for x in df["label"].fillna("").astype(str).unique() if str(x)})
    if experiment:
        work = work[work["experiment"].astype(str) == experiment]
    if protocol:
        work = work[work["protocol"].astype(str) == protocol]
    if model:
        work = work[work["model"].fillna("").astype(str) == model]
    if label:
        work = work[work["label"].fillna("").astype(str) == label]
    total = int(len(work))
    page = work.iloc[offset : offset + limit]
    rows = []
    for _, row in page.iterrows():
        value = _nan_to_none(row.get("value"))
        if value is None:
            continue
        rows.append(
            RunRow(
                experiment=str(row.get("experiment", "")),
                protocol=str(row.get("protocol", "")),
                reference=str(row.get("reference", "")),
                features=str(row.get("features", "") or ""),
                model=str(row.get("model", "") or ""),
                label=str(row.get("label", "") or ""),
                metric=str(row.get("metric", "")),
                value=value,
                n=_int_or_none(row.get("n")),
                note=str(row.get("note", "") or ""),
            )
        )
    return EvidenceRuns(
        total=total,
        offset=offset,
        limit=limit,
        rows=rows,
        experiments=experiments,
        protocols=protocols,
        models=models,
        labels=labels,
    )


@router.get(
    "/confusion",
    response_model=EvidenceConfusion,
    summary="Confusion matrix for a named protocol",
    operation_id="getEvidenceConfusion",
)
def evidence_confusion(
    settings: Settings = Depends(get_settings),
    protocol: str = Query("holdout-test"),
) -> EvidenceConfusion:
    if protocol == "sim2real":
        path = (settings.confusion_path.parent / "confusion_sim2real.csv") if settings.confusion_path else None
        artefact = "confusion_sim2real.csv"
    else:
        path = settings.confusion_path
        protocol = "holdout-test"
        artefact = "confusion_matrix.csv"
    if path is None or not path.exists():
        raise ArtifactMissing(artefact)
    table = pd.read_csv(path, index_col=0)
    labels = [str(c) for c in table.columns]
    if set(labels).issubset(set(map(str, table.index))):
        table = table.loc[labels, labels]
    matrix = table.astype(float).values.tolist()
    try:
        source = str(path.relative_to(ROOT))
    except ValueError:
        source = path.name
    return EvidenceConfusion(
        protocol=protocol,
        labels=labels,
        matrix=matrix,
        source=source,
    )
