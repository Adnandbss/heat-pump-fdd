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
    CalibrationPoint,
    DomainBar,
    EvidenceCalibration,
    EvidenceConfusion,
    EvidenceDomain,
    EvidenceFeatures,
    EvidenceLadder,
    EvidencePerClass,
    EvidenceProtocols,
    EvidenceReferences,
    EvidenceRules,
    EvidenceRuns,
    EvidenceSummary,
    FeatureSlopePoint,
    LadderRung,
    PerClassScores,
    ProtocolRef,
    ProtocolSlopePoint,
    ReferencePoint,
    RulesBar,
    RunRow,
    SeverityPair,
    SummaryCard,
    WilsonInterval,
)
from api.settings import ROOT, Settings

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

_REF_RE = re.compile(
    r"^(?P<family>.+)-(?P<conditioning>TT|TTdew)-dmin(?P<dmin>[0-9.]+)$"
)
_KNN_FACET = re.compile(r"^(knn-k\d+)-median-unif$")
_WILSON_RE = re.compile(r"\[(\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\]")

# Experiments a figure endpoint selects. The coverage test compares this to results.csv.
# X3-prelim (6 rows) is deliberately not plotted: it is the preliminary pass that
# X3 (505 rows) supersedes. Coverage is therefore 8 experiments out of 9.
EXCLUDED_FROM_FIGURES = {"X3-prelim"}
FIGURE_EXPERIMENTS = {
    "ladder": {"X0", "X0b", "X1", "X5"},
    "protocols": {"X0b"},
    "references": {"X3"},
    "per-class": {"X1", "X5"},
    "domain": {"X4"},
    "features": {"P5"},
    "rules": {"X2"},
    "calibration": {"X1"},
}

_DOMAIN_BARS = [
    ("holdout-random-control", "Random (control)"),
    ("holdout-domain-speed>0.85", "speed > 0.85"),
    ("holdout-domain-GroupKFold", "GroupKFold 5-fold"),
    ("holdout-domain-Tamb<-5", "T_amb < −5 °C"),
    ("holdout-domain-Tsink>48", "T_sink > 48 °C"),
]
_SEVERITY_PAIRS = [
    {
        "key": "severe-to-emerging",
        "label": "severe → emerging",
        "binary": "holdout-binary-severity-train>=0.20",
        "multiclass": "holdout-severity-4class-<0.20",
    },
    {
        "key": "emerging-to-severe",
        "label": "emerging → severe",
        "binary": "holdout-binary-severity-train<0.20",
        "multiclass": "holdout-severity-4class->=0.20",
    },
]
_FEATURE_SETS = ["23-col", "23-col-minus-dead", "residuals", "residuals+conditions"]
_RULE_BARS = [
    ("rule-table", "Sign table"),
    ("decision-tree-d3", "Depth-3 tree"),
    ("gradient-boosting", "Gradient boosting"),
]


def covered_experiments() -> set:
    """Union of experiments a figure endpoint looks up."""
    selected: set = set()
    for names in FIGURE_EXPERIMENTS.values():
        selected.update(names)
    return selected

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
        "cause": "d_COP leaked the label",
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
        "cause": "6 classes, including one unmodelled ghost",
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
        "cause": "7 classes, honest hold-out",
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
        "cause": "LOMO, residuals, healthy reference on the target machine",
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
        "cause": "sim2real: trained on the simulator, tested on measured data",
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
        "cause": "LOMO, healthy reference transferred from another machine",
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
        "cause": "majority class",
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


def _wilson(note: Any) -> Optional[WilsonInterval]:
    if note is None:
        return None
    match = _WILSON_RE.search(str(note))
    if not match:
        return None
    low, high = float(match.group(1)), float(match.group(2))
    if low > 1.0 or high > 1.0:
        low, high = low / 100.0, high / 100.0
    return WilsonInterval(low=low, high=high)


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
        badge=ProtocolRef(
            experiment="X3",
            protocol="LOMO",
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
        ),
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


@router.get(
    "/domain",
    response_model=EvidenceDomain,
    summary="X4: domain hold-out vs severity transfer",
    operation_id="getEvidenceDomain",
)
def evidence_domain(df: pd.DataFrame = Depends(get_results)) -> EvidenceDomain:
    domain: List[DomainBar] = []
    for protocol, label in _DOMAIN_BARS:
        row = _match(
            df,
            {
                "experiment": "X4",
                "protocol": protocol,
                "reference": "simulated",
                "model": "random-forest",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        if row is None:
            continue
        value = _nan_to_none(row["value"])
        if value is None:
            continue
        domain.append(
            DomainBar(
                key=protocol,
                label=label,
                accuracy=value,
                n=_int_or_none(row.get("n")),
                wilson=_wilson(row.get("note")),
                protocol=_protocol(row),
            )
        )
    severity: List[SeverityPair] = []
    for spec in _SEVERITY_PAIRS:
        binary = _match(
            df,
            {
                "experiment": "X4",
                "protocol": spec["binary"],
                "reference": "simulated",
                "model": "random-forest",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        multi = _match(
            df,
            {
                "experiment": "X4",
                "protocol": spec["multiclass"],
                "reference": "simulated",
                "model": "random-forest",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        severity.append(
            SeverityPair(
                key=spec["key"],
                label=spec["label"],
                binary=_nan_to_none(binary["value"]) if binary is not None else None,
                multiclass=_nan_to_none(multi["value"]) if multi is not None else None,
                n_binary=_int_or_none(binary.get("n")) if binary is not None else None,
                n_multiclass=_int_or_none(multi.get("n")) if multi is not None else None,
                binary_protocol=_protocol(binary) if binary is not None else None,
                multiclass_protocol=_protocol(multi) if multi is not None else None,
            )
        )
    return EvidenceDomain(
        domain=domain,
        severity=severity,
        caption="The model knows something is wrong; it no longer knows what.",
        badge=ProtocolRef(
            experiment="X4",
            protocol="holdout-domain",
            reference="simulated",
            features="24-col",
            model="random-forest",
        ),
    )


@router.get(
    "/features",
    response_model=EvidenceFeatures,
    summary="P5: feature-contract slopegraph",
    operation_id="getEvidenceFeatures",
)
def evidence_features(df: pd.DataFrame = Depends(get_results)) -> EvidenceFeatures:
    series: List[FeatureSlopePoint] = []
    for features in _FEATURE_SETS:
        holdout = _match(
            df,
            {
                "experiment": "P5",
                "protocol": "holdout-test",
                "reference": "simulated",
                "features": features,
                "model": "random-forest",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        domain = _match(
            df,
            {
                "experiment": "P5",
                "protocol": "holdout-domain-Tset>48",
                "reference": "simulated",
                "features": features,
                "model": "random-forest",
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        if holdout is None and domain is None:
            continue
        series.append(
            FeatureSlopePoint(
                features=features,
                holdout=_nan_to_none(holdout["value"]) if holdout is not None else None,
                domain=_nan_to_none(domain["value"]) if domain is not None else None,
                protocol_holdout=_protocol(holdout) if holdout is not None else None,
                protocol_domain=_protocol(domain) if domain is not None else None,
            )
        )
    return EvidenceFeatures(
        series=series,
        note="Residuals-only was prescribed, measured, and rejected.",
        badge=ProtocolRef(
            experiment="P5",
            protocol="holdout-test",
            reference="simulated",
            features="23-col",
            model="random-forest",
        ),
    )


@router.get(
    "/rules",
    response_model=EvidenceRules,
    summary="X2: sign table vs tree vs boosting",
    operation_id="getEvidenceRules",
)
def evidence_rules(df: pd.DataFrame = Depends(get_results)) -> EvidenceRules:
    bars: List[RulesBar] = []
    for model, label in _RULE_BARS:
        row = _match(
            df,
            {
                "experiment": "X2",
                "protocol": "LOMO",
                "reference": "target-machine",
                "features": "residuals",
                "model": model,
                "label": "__global__",
                "metric": "accuracy",
            },
        )
        if row is None:
            continue
        bars.append(
            RulesBar(
                model=model,
                label=label,
                accuracy=_nan_to_none(row["value"]),
                protocol=_protocol(row),
            )
        )
    majority_row = _match(
        df,
        {
            "experiment": "X2",
            "protocol": "majority-class",
            "reference": "none",
            "features": "",
            "model": "baseline",
            "label": "__global__",
            "metric": "accuracy",
        },
    )
    return EvidenceRules(
        bars=bars,
        majority=_nan_to_none(majority_row["value"]) if majority_row is not None else None,
        majority_protocol=_protocol(majority_row) if majority_row is not None else None,
        badge=ProtocolRef(
            experiment="X2",
            protocol="LOMO",
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
        ),
    )


_CALIBRATION_POINTS = [
    {
        "n_label": "0",
        "n_healthy": 0,
        "lookup": {
            "experiment": "X1",
            "protocol": "LOMO",
            "reference": "training-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
        },
    },
    {
        "n_label": "10",
        "n_healthy": 10,
        "lookup": {
            "experiment": "X1",
            "protocol": "LOMO-calibration-n10",
            "reference": "target-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
        },
    },
    {
        "n_label": "50",
        "n_healthy": 50,
        "lookup": {
            "experiment": "X1",
            "protocol": "LOMO-calibration-n50",
            "reference": "target-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
        },
    },
    {
        "n_label": "all",
        "n_healthy": None,
        "lookup": {
            "experiment": "X0b",
            "protocol": "LOMO",
            "reference": "target-machine",
            "features": "residuals",
            "model": "gradient-boosting",
            "label": "__global__",
        },
    },
]


@router.get(
    "/calibration",
    response_model=EvidenceCalibration,
    summary="X1: healthy-calibration budget on the target machine",
    operation_id="getEvidenceCalibration",
)
def evidence_calibration(df: pd.DataFrame = Depends(get_results)) -> EvidenceCalibration:
    points: List[CalibrationPoint] = []
    for spec in _CALIBRATION_POINTS:
        acc = _match(df, {**spec["lookup"], "metric": "accuracy"})
        f1 = _match(df, {**spec["lookup"], "metric": "f1"})
        if acc is None and f1 is None:
            continue
        points.append(
            CalibrationPoint(
                n_label=spec["n_label"],
                n_healthy=spec["n_healthy"],
                accuracy=_nan_to_none(acc["value"]) if acc is not None else None,
                f1=_nan_to_none(f1["value"]) if f1 is not None else None,
                protocol=_protocol(acc if acc is not None else f1),
            )
        )
    return EvidenceCalibration(
        points=points,
        caption="Fifty healthy tests recover about half the gap. Covering the envelope is the constraint.",
        badge=ProtocolRef(
            experiment="X1",
            protocol="LOMO-calibration-n50",
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
        ),
    )
