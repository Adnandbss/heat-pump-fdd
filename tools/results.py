"""Single source of truth for measured results.

Every experiment appends its numbers here instead of leaving them in a notebook
output. Documentation then cites this file rather than re-typing figures — which
is how the repository ended up contradicting itself twice.

    from tools.results import log

    log(experiment="X1", protocol="LOMO", reference="target-machine",
        features="residuals", label="Undercharge", metric="f1", value=0.832)

The protocol columns are mandatory on purpose: a number without its protocol is
not a result, and this project has measured how much that matters.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "outputs" / "results.csv"

COLUMNS = [
    "experiment",   # X1, X2, ... — which experiment produced this
    "protocol",     # LOMO, random-cv, holdout-domain, ...
    "reference",    # target-machine, training-machine, none, simulated, ...
    "features",     # residuals, raw, raw+residuals, ...
    "model",        # gradient-boosting, rule-table, decision-tree-d3, ...
    "label",        # a class name, or __global__
    "metric",       # accuracy, f1, precision, recall, ...
    "value",
    "n",            # support, when it applies
    "note",
]

_KEY = ("experiment", "protocol", "reference", "features", "model", "label", "metric")


def _read() -> list[dict]:
    if not RESULTS_PATH.exists():
        return []
    with RESULTS_PATH.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def log(
    *,
    experiment: str,
    protocol: str,
    reference: str,
    metric: str,
    value: float,
    features: str = "",
    model: str = "",
    label: str = "__global__",
    n: Optional[int] = None,
    note: str = "",
) -> None:
    """Append one measured number, replacing any earlier row with the same key."""
    row = {
        "experiment": experiment, "protocol": protocol, "reference": reference,
        "features": features, "model": model, "label": label, "metric": metric,
        "value": f"{float(value):.6g}", "n": "" if n is None else str(int(n)),
        "note": note,
    }
    key = tuple(row[c] for c in _KEY)
    rows = [r for r in _read() if tuple(r[c] for c in _KEY) != key]
    rows.append(row)
    rows.sort(key=lambda r: tuple(r[c] for c in _KEY))
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def get(**filters) -> list[dict]:
    """Rows matching every given column, for docs or figures to read back."""
    return [r for r in _read() if all(r.get(k) == str(v) for k, v in filters.items())]


def value(**filters) -> float:
    """Exactly one matching row, as a float. Raises if ambiguous or missing."""
    rows = get(**filters)
    if len(rows) != 1:
        raise LookupError(f"{len(rows)} rows match {filters}; expected exactly 1")
    return float(rows[0]["value"])
