"""Fleet triage policy: which diagnosis earns a service dispatch.

A fault class only triggers a dispatch when the logged evidence says the
simulator-trained classifier still finds it on measured units. The two
thresholds are product decisions, justified in docs/product/PRD.md.

The queue agent is eager: it proposes the action it would take with the
evidence gate off. The rule then keeps or refuses that proposal. A language
model may rephrase the installer sentence. It cannot change the action.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional

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
) -> tuple[str, str, str, Evidence]:
    """Allowed action, eager proposal, installer sentence, and evidence.

    The proposal is what the agent wants with the gate off. The allowed action
    is what the rule permits.
    """
    evidence = evidence_for(label, evidence_by_class(results))
    proposed = decide(label, confidence, evidence, validated_only=False)
    action = decide(label, confidence, evidence, validated_only)
    sentence = rewrite_instruction(action, label, instruction(action, label))
    return action, proposed, sentence, evidence


def instruction(action: str, label: str) -> str:
    if action == DISPATCH:
        return DISPATCH_INSTRUCTIONS.get(label, "Dispatch an installer to inspect the unit.")
    return INSTRUCTIONS[action]


def rewrite_instruction(
    action: str,
    label: str,
    fallback: str,
    complete: Optional[Callable[[str, str, str, str], str]] = None,
) -> str:
    """Rephrase the installer sentence. The decided action is not negotiable.

    With `FDD_INSTRUCTION_MODEL` unset, the fixed sentence is returned and
    nothing is sent over the network.
    """
    model = os.environ.get("FDD_INSTRUCTION_MODEL", "").strip()
    if not model:
        return fallback
    caller = complete or _complete_instruction
    try:
        rewritten = caller(model, action, label, fallback)
    except Exception:
        return fallback
    if not rewritten or action not in rewritten:
        return fallback
    return rewritten


def _complete_instruction(model: str, action: str, label: str, fallback: str) -> str:
    """One chat completion. Used only when FDD_INSTRUCTION_MODEL is set."""
    key = os.environ.get("FDD_INSTRUCTION_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FDD_INSTRUCTION_API_KEY is not set")
    url = os.environ.get("FDD_INSTRUCTION_API_URL", "https://api.openai.com/v1/chat/completions")
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Rewrite the installer instruction in one sentence. "
                    f"The decision is already {action}. Include that exact word. "
                    "Do not recommend a different action."
                ),
            },
            {"role": "user", "content": f"Fault: {label}. Instruction: {fallback}"},
        ],
    }).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())
    return str(payload["choices"][0]["message"]["content"]).strip()
