"""Fleet triage policy: which diagnosis earns a service dispatch.

A fault class only triggers a dispatch when the logged evidence says the
simulator-trained classifier still finds it on measured units. The two
thresholds are product decisions, justified in docs/product/PRD.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

EVIDENCE_EXPERIMENT = "X5"
EVIDENCE_PROTOCOL = "sim2real"
EVIDENCE_F1_MIN = 0.40
CONFIDENCE_MIN = 0.60

TRANSFERS = "transfers"
DOES_NOT_TRANSFER = "does_not_transfer"
UNTESTED = "untested"

DISPATCH = "dispatch"
ENGINEERING_REVIEW = "engineering_review"
MONITOR = "monitor"
NO_ACTION = "no_action"

PRIORITY = {DISPATCH: 0, ENGINEERING_REVIEW: 1, MONITOR: 2, NO_ACTION: 3}

HEALTHY = "Normal"

DISPATCH_INSTRUCTIONS = {
    "Refrigerant_Undercharge": "Leak search, repair, then recharge to the nameplate charge.",
    "Refrigerant_Overcharge": "Recover refrigerant down to the nameplate charge.",
    "Condenser_Fouling": "Clean the condenser heat exchanger.",
    "Evaporator_Fouling": "Clean the evaporator coil.",
    "Condenser_Fan_Fault": "Inspect the condenser fan and its motor.",
    "Evaporator_Fan_Fault": "Inspect the evaporator fan and its motor.",
}

INSTRUCTIONS = {
    NO_ACTION: "No action.",
    MONITOR: "Low confidence: re-check at the next steady-state window.",
    ENGINEERING_REVIEW: (
        "Not validated on measured units: route to engineering, "
        "do not dispatch on this alert alone."
    ),
}


@dataclass(frozen=True)
class Evidence:
    status: str
    f1: Optional[float] = None
    n: Optional[int] = None


def evidence_by_class(results: pd.DataFrame) -> Dict[str, Evidence]:
    """Per-class transfer status from the X5 sim2real F1 rows of results.csv."""
    if results.empty:
        return {}
    rows = results[
        (results["experiment"] == EVIDENCE_EXPERIMENT)
        & (results["protocol"] == EVIDENCE_PROTOCOL)
        & (results["metric"] == "f1")
        & (results["label"] != "__global__")
    ]
    table: Dict[str, Evidence] = {}
    for _, row in rows.iterrows():
        f1 = float(row["value"])
        n = row.get("n")
        status = TRANSFERS if f1 >= EVIDENCE_F1_MIN else DOES_NOT_TRANSFER
        table[str(row["label"])] = Evidence(
            status=status,
            f1=f1,
            n=None if n is None or (isinstance(n, float) and math.isnan(n)) else int(n),
        )
    return table


def evidence_for(label: str, table: Dict[str, Evidence]) -> Evidence:
    return table.get(label, Evidence(status=UNTESTED))


def decide(label: str, confidence: float, evidence: Evidence, validated_only: bool) -> str:
    if label == HEALTHY:
        return MONITOR if confidence < CONFIDENCE_MIN else NO_ACTION
    if validated_only and evidence.status != TRANSFERS:
        return ENGINEERING_REVIEW
    if confidence < CONFIDENCE_MIN:
        return MONITOR
    return DISPATCH


def service_decision(
    label: str, confidence: float, results: pd.DataFrame, validated_only: bool
) -> tuple[str, str, Evidence]:
    """Action, installer instruction, and evidence for one diagnosis."""
    evidence = evidence_for(label, evidence_by_class(results))
    action = decide(label, confidence, evidence, validated_only)
    return action, instruction(action, label), evidence


def instruction(action: str, label: str) -> str:
    if action == DISPATCH:
        return DISPATCH_INSTRUCTIONS.get(label, "Dispatch an installer to inspect the unit.")
    return INSTRUCTIONS[action]
