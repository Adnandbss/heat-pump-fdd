"""P5 — feature-contract comparison. Measure first, then decide.

Four contracts × two protocols, production RF pipeline, same seed as X0.
Does not write the shipped model. Does not regenerate the production dataset.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fdd.ml_models import FDDClassifier, wilson_ci
from src.studies.synthetic.paths import DATASET_PATH
from tools.results import log

TABLE = ROOT / "outputs" / "p5_feature_contracts.csv"
SEED = 42

ALL_24 = [
    "T_ambient", "T_setpoint", "compressor_speed_ratio",
    "P_evap", "P_cond", "T_evap", "T_cond", "T_suction", "T_discharge",
    "superheat", "subcooling", "compression_ratio", "W_comp", "Q_cond", "COP",
    "delta_T_evap", "delta_T_cond", "pressure_ratio", "capacity_ratio",
    "d_T_discharge", "d_superheat", "d_subcooling", "d_COP", "d_W_comp",
]
CURRENT_23 = [c for c in ALL_24 if c != "pressure_ratio"]
RESIDUALS = ["d_T_discharge", "d_superheat", "d_subcooling", "d_COP", "d_W_comp"]
RESIDUALS_PLUS_COND = ["T_ambient", "T_setpoint", "compressor_speed_ratio", *RESIDUALS]
DEAD = [
    "T_ambient", "Q_cond", "W_comp", "T_setpoint",
    "compressor_speed_ratio", "capacity_ratio",
]
MINUS_DEAD = [c for c in CURRENT_23 if c not in DEAD]

CONTRACTS = {
    "24-col": ALL_24,
    "23-col": CURRENT_23,
    "residuals+conditions": RESIDUALS_PLUS_COND,
    "residuals": RESIDUALS,
    "23-col-minus-dead": MINUS_DEAD,
}

# Part 2 published set — 24-col is the Part 1 control only.
PART2 = ("23-col", "residuals+conditions", "residuals", "23-col-minus-dead")


def _fit(X_tr, y_tr, cols):
    clf = FDDClassifier(model_type="random_forest", random_state=SEED)
    clf._estimator.set_params(n_jobs=1)
    clf.fit(X_tr, y_tr, feature_columns=list(cols))
    return clf


def _pack(clf, X_te, y_te, X_va=None, y_va=None):
    pred = clf.predict(X_te)
    acc = float(accuracy_score(y_te, pred))
    f1 = float(f1_score(y_te, pred, average="macro", zero_division=0))
    n = int(len(y_te))
    lo, hi = wilson_ci(acc, n)
    val_f1 = None
    if X_va is not None:
        val_f1 = float(f1_score(y_va, clf.predict(X_va), average="macro", zero_division=0))
    return {
        "accuracy": acc, "f1": f1, "n": n, "ci_low": lo, "ci_high": hi,
        "val_f1": val_f1, "majority": float(pd.Series(y_te).value_counts(normalize=True).max()),
    }


def random_holdout(df: pd.DataFrame, cols):
    y = df["fault_type"]
    X = df[cols]
    X_trv, X_te, y_trv, y_te = train_test_split(
        X, y, test_size=0.30, random_state=SEED, stratify=y,
    )
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_trv, y_trv, test_size=0.25, random_state=SEED, stratify=y_trv,
    )
    clf = _fit(X_tr, y_tr, cols)
    return _pack(clf, X_te, y_te, X_va, y_va)


def domain_holdout(df: pd.DataFrame, cols, mask: pd.Series):
    y = df["fault_type"]
    te, trv = mask, ~mask
    X_tr, X_va, y_tr, y_va = train_test_split(
        df.loc[trv, cols], y[trv], test_size=0.25, random_state=SEED, stratify=y[trv],
    )
    clf = _fit(X_tr, y_tr, cols)
    packed = _pack(clf, df.loc[te, cols], y[te], X_va, y_va)
    packed["n_trainval"] = int(trv.sum())
    return packed


def _log(protocol: str, features: str, scores: dict, note: str = ""):
    log(
        experiment="P5", protocol=protocol, reference="simulated",
        features=features, model="random-forest",
        metric="accuracy", value=scores["accuracy"], n=scores["n"],
        note=note or (
            f"95% Wilson CI [{scores['ci_low']:.3f}, {scores['ci_high']:.3f}]; "
            f"F1={scores['f1']:.3f}; majority={scores['majority']:.3f}"
        ),
    )
    log(
        experiment="P5", protocol=protocol, reference="simulated",
        features=features, model="random-forest",
        metric="f1", value=scores["f1"], n=scores["n"],
        note="macro; selected on val",
    )


def intervals_overlap(a: dict, b: dict) -> bool:
    return a["ci_low"] <= b["ci_high"] and b["ci_low"] <= a["ci_high"]


def main():
    df = pd.read_csv(DATASET_PATH)
    dup = (df.compression_ratio - df.pressure_ratio).abs()
    print(f"dataset {len(df)} × {df.shape[1]}")
    print(f"compression_ratio ≡ pressure_ratio : max |Δ|={dup.max():.2e}  "
          f"identical={(dup == 0).mean():.1%}")
    if dup.max() > 1e-12:
        raise SystemExit("the two ratios are not identical — stop")

    print(f"minus-dead columns ({len(MINUS_DEAD)}): {MINUS_DEAD}")
    assert len(CURRENT_23) == 23
    assert len(MINUS_DEAD) == 17
    assert len(RESIDUALS) == 5
    assert len(RESIDUALS_PLUS_COND) == 8

    mask = df["T_setpoint"] > 48.0
    print(f"T_setpoint > 48 °C : {int(mask.sum())} test / {int((~mask).sum())} trainval")

    rows = []
    store = {}
    for proto, runner in (
        ("holdout-test", lambda cols: random_holdout(df, cols)),
        ("holdout-domain-Tset>48", lambda cols: domain_holdout(df, cols, mask)),
    ):
        print(f"\n=== {proto} ===")
        names = ("24-col", *PART2) if proto == "holdout-test" else PART2
        for name in names:
            scores = runner(CONTRACTS[name])
            store[(proto, name)] = scores
            print(
                f"  {name:24s}  acc={scores['accuracy']:.4f} "
                f"[{scores['ci_low']:.3f}, {scores['ci_high']:.3f}]  "
                f"F1={scores['f1']:.3f}  n={scores['n']}"
            )
            note = (
                f"95% Wilson CI [{scores['ci_low']:.3f}, {scores['ci_high']:.3f}]; "
                f"F1={scores['f1']:.3f}"
            )
            if name != "24-col":
                _log(proto, name, scores, note=note)
            rows.append({
                "protocol": proto, "contract": name, "n_features": len(CONTRACTS[name]),
                **{k: scores[k] for k in ("accuracy", "ci_low", "ci_high", "f1", "n", "majority")},
            })

    # Part 1 gate: 23-col must stay inside the 24-col interval.
    a24 = store[("holdout-test", "24-col")]
    a23 = store[("holdout-test", "23-col")]
    delta = abs(a23["accuracy"] - a24["accuracy"])
    half = (a24["ci_high"] - a24["ci_low"]) / 2
    print(f"\nPart 1  |Δ acc 24→23|={delta:.4f}  half-CI={half:.4f}")
    if delta > half:
        raise SystemExit(
            f"23-col moved by {delta:.4f}, more than the 24-col CI half-width "
            f"{half:.4f} — something else changed"
        )
    print("Part 1 OK — dropping the duplicate stays inside the interval.")

    print("\nPart 2 — pairwise CI overlap")
    keep = True
    for proto in ("holdout-test", "holdout-domain-Tset>48"):
        base = store[(proto, "23-col")]
        for name in PART2:
            other = store[(proto, name)]
            ok = intervals_overlap(base, other)
            print(f"  {proto:24s}  23-col vs {name:24s}  overlap={ok}")
            if name != "23-col" and not ok and other["accuracy"] > base["accuracy"]:
                keep = False
    if keep:
        print("\nDecision: KEEP 23-col. Leaner contracts do not beat it outside its interval.")
    else:
        print("\nDecision: a leaner contract beat 23-col outside the interval — review before applying.")

    TABLE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(TABLE, index=False)
    print(f"\ntable → {TABLE}")
    return store


if __name__ == "__main__":
    main()
