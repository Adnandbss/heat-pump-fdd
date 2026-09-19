"""X5 — does the simulator describe a real machine?

Train on cycles simulated at NIST conditions, test on measured tests.
Three protocols, same five classes, same residual features, same RF Pipeline.

Do not touch simulator.py, generator.py, the production dataset, or the shipped model.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "EDA"))

from src.fdd.ml_models import FDDClassifier, wilson_ci
from src.physics.simulator import HeatPumpSimulator
from src.studies.synthetic.generator import FaultDataGenerator, FaultType
from tools.results import log
from x3_compute import COND2, knn_estimate, load as load_nist_x3

NIST = ROOT / "data" / "nist"
TABLE = ROOT / "outputs" / "x5_sim2real.csv"
PERCLASS = ROOT / "outputs" / "x5_sim2real_perclass.csv"
FIG = ROOT / "docs" / "nist_x5_sim2real.png"
SIM_CSV = ROOT / "outputs" / "x5_sim_nist_domain.csv"

assert (NIST / "fdd_1416seer.xlsx").exists(), "place fdd_1416seer.xlsx in data/nist/"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})

# Cooling: indoor coil = evaporator = T_source, outdoor coil = condenser = T_sink.
# Same mapping as X3. CF is outdoor-coil blockage → Condenser_Fouling, not evap fouling.
NIST_TO_SIM = {
    "No_Fault": "Normal",
    "Cond_Blockage": "Condenser_Fouling",
    "Evap_Airflow": "Evaporator_Fan_Fault",
    "Undercharge": "Refrigerant_Undercharge",
    "Overcharge": "Refrigerant_Overcharge",
}
SIM_CLASSES = list(NIST_TO_SIM.values())
RES5 = ["T_discharge", "superheat", "subcooling", "COP", "W_comp"]
DCOLS = ["d_T_discharge", "d_superheat", "d_subcooling", "d_COP", "d_W_comp"]

T_SOURCE_SPEC = (14.0, 26.0)
T_SINK_SPEC = (19.0, 48.0)
T_SOURCE_NIST_MAX = 26.0
T_EVAP_CLIP = 20.0
N_SIM = 5000
SEED = 42

FIVE_CLASS_MIX = {
    FaultType.NORMAL: 0.40,
    FaultType.CONDENSER_FOULING: 0.15,
    FaultType.EVAPORATOR_FAN_FAULT: 0.15,
    FaultType.REFRIGERANT_UNDERCHARGE: 0.15,
    FaultType.REFRIGERANT_OVERCHARGE: 0.15,
}


def clip_probe(T_sink: float = 35.0) -> pd.DataFrame:
    """Does T_evap sit on the 20 °C cap? Do not assume — measure."""
    sim = HeatPumpSimulator()
    rows = []
    for ts in (20.0, 24.0, 25.0, 26.0, 27.0, 30.0):
        r = sim.simulate_cycle(T_source=ts, T_sink=T_sink, speed_ratio=1.0)
        clipped = bool(np.isclose(r.T_evap, sim.T_evap_max, atol=1e-9))
        rows.append({
            "T_source": ts, "T_sink": T_sink, "T_evap": float(r.T_evap),
            "clipped": clipped, "P_evap": float(r.P_evap), "P_cond": float(r.P_cond),
            "tau": float(r.P_cond / r.P_evap), "COP": float(r.COP),
        })
    return pd.DataFrame(rows)


def safe_T_source_hi(T_sink: float = 35.0, step: float = 0.1) -> float:
    """Largest T_source whose healthy cycle does not sit on T_evap_max."""
    sim = HeatPumpSimulator()
    hi = T_SOURCE_SPEC[0]
    ts = T_SOURCE_SPEC[0]
    while ts <= T_SOURCE_SPEC[1] + 1e-9:
        r = sim.simulate_cycle(T_source=ts, T_sink=T_sink, speed_ratio=1.0)
        if np.isclose(r.T_evap, sim.T_evap_max, atol=1e-9):
            break
        hi = ts
        ts += step
    return float(hi)


def generate_sim_at_nist_conditions(n: int = N_SIM, T_source_hi: float | None = None) -> pd.DataFrame:
    """Same generator, ranges passed in. Do not edit generator.py."""
    gen = FaultDataGenerator(random_seed=SEED)
    hi = T_SOURCE_SPEC[1] if T_source_hi is None else T_source_hi
    gen.T_source_range = (T_SOURCE_SPEC[0], hi)
    gen.T_sink_range = T_SINK_SPEC
    gen.speed_ratio_range = (1.0, 1.0)  # NIST units are single-speed
    df = gen.generate_dataset(
        n_samples=n,
        fault_distribution=FIVE_CLASS_MIX,
        show_progress=True,
    )
    return df


def nist_five_class(T_source_max: float = T_SOURCE_NIST_MAX):
    """Measured rows, five matching classes, T_source cap, measured knn5 residuals."""
    X, y_nist, grp = load_nist_x3()
    X = X.copy()
    X["W_comp"] = X["W_od"]
    mapped = y_nist.map(NIST_TO_SIM)
    keep = mapped.notna() & (X["T_source"] <= T_source_max)
    X, y, grp = X.loc[keep].copy(), mapped.loc[keep].copy(), grp.loc[keep].copy()

    leak = ["EF", "CF", "LL", "UC/OC", "NF"]
    assert not any(c in X.columns for c in leak)

    D = pd.DataFrame(index=X.index, columns=DCOLS, dtype=float)
    for seer in (14.0, 16.0):
        mask = grp == seer
        healthy = mask & (y == "Normal")
        pred = knn_estimate(
            X.loc[healthy, COND2], X.loc[healthy, RES5],
            X.loc[mask, COND2], k=5, agg="median",
        )
        D.loc[mask, DCOLS] = X.loc[mask, RES5].to_numpy() - pred
    feat = D.copy()
    feat["T_source"] = X["T_source"]
    feat["T_sink"] = X["T_sink"]
    return feat, y, grp, X


def _fit_rf(X: pd.DataFrame, y: pd.Series) -> FDDClassifier:
    clf = FDDClassifier("random_forest", random_state=SEED)
    clf._estimator.n_jobs = 1
    clf.model = clf._make_pipeline(clf._estimator)
    clf.fit(X[DCOLS], y, feature_columns=DCOLS)
    return clf


def _scores(y_true, y_hat, labels=SIM_CLASSES):
    y_true = np.asarray(y_true)
    y_hat = np.asarray(y_hat)
    n = int(len(y_true))
    acc = float(accuracy_score(y_true, y_hat))
    f1 = float(f1_score(y_true, y_hat, average="macro", zero_division=0, labels=labels))
    lo, hi = wilson_ci(acc, n)
    maj = float(pd.Series(y_true).value_counts(normalize=True).max())
    p, r, f1c, sup = precision_recall_fscore_support(
        y_true, y_hat, labels=labels, zero_division=0,
    )
    per = [
        {"label": lab, "precision": float(pi), "recall": float(ri),
         "f1": float(fi), "n": int(si)}
        for lab, pi, ri, fi, si in zip(labels, p, r, f1c, sup)
    ]
    return {
        "accuracy": acc, "f1": f1, "ci_low": lo, "ci_high": hi,
        "n": n, "majority": maj, "per_class": per,
        "y_true": y_true, "y_hat": y_hat,
    }


def _log_block(protocol: str, reference: str, features: str, scores: dict, note: str = ""):
    log(
        experiment="X5", protocol=protocol, reference=reference,
        features=features, model="random-forest",
        metric="accuracy", value=scores["accuracy"], n=scores["n"],
        note=note or (
            f"95% Wilson CI [{scores['ci_low']:.3f}, {scores['ci_high']:.3f}]; "
            f"F1={scores['f1']:.3f}; majority={scores['majority']:.3f}"
        ),
    )
    log(
        experiment="X5", protocol=protocol, reference=reference,
        features=features, model="random-forest",
        metric="f1", value=scores["f1"], n=scores["n"],
        note="macro",
    )
    for row in scores["per_class"]:
        log(
            experiment="X5", protocol=protocol, reference=reference,
            features=features, model="random-forest",
            label=row["label"], metric="f1", value=row["f1"], n=row["n"],
        )


def ensure_x0_readme_logs() -> None:
    """Percents cited in README Results must exist in results.csv (the X5 guard)."""
    cmp_path = ROOT / "outputs" / "synthetic" / "model_comparison.csv"
    if cmp_path.exists():
        cmp = pd.read_csv(cmp_path)
        gb = cmp.loc[cmp["Model"] == "Gradient Boosting"].iloc[0]
        log(
            experiment="X0", protocol="holdout-test", reference="simulated",
            features="24-col", model="gradient-boosting",
            metric="accuracy", value=float(gb["Accuracy"]), n=int(gb["n_test"]),
            note=(
                f"95% Wilson CI [{float(gb['Accuracy_CI_low']):.3f}, "
                f"{float(gb['Accuracy_CI_high']):.3f}]; selected on val"
            ),
        )
        log(
            experiment="X0", protocol="holdout-test", reference="simulated",
            features="24-col", model="gradient-boosting",
            metric="f1", value=float(gb["F1 Score"]), n=int(gb["n_test"]),
            note="macro; selected on val",
        )
    log(
        experiment="X0", protocol="holdout-test-6class", reference="simulated",
        features="24-col", model="random-forest",
        metric="accuracy", value=0.9187, n=1500,
        note="P0 six-class; 95% Wilson CI [0.904, 0.931]; superseded by seven-class",
    )
    log(
        experiment="X0", protocol="leaked-dCOP", reference="simulated",
        features="24-col", model="random-forest",
        metric="accuracy", value=0.996, n=5000,
        note="withdrawn: d_COP equalled the detection label",
    )


def sim_holdout(df: pd.DataFrame) -> dict:
    X, y = df[DCOLS], df["fault_type"]
    X_trv, X_te, y_trv, y_te = train_test_split(
        X, y, test_size=0.30, random_state=SEED, stratify=y,
    )
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_trv, y_trv, test_size=0.25, random_state=SEED, stratify=y_trv,
    )
    clf = _fit_rf(X_tr, y_tr)
    val_f1 = float(f1_score(y_va, clf.predict(X_va), average="macro", zero_division=0))
    scores = _scores(y_te, clf.predict(X_te))
    scores["val_f1"] = val_f1
    scores["clf"] = clf
    return scores


def lomo_measured(feat: pd.DataFrame, y: pd.Series, grp: pd.Series) -> dict:
    y_true, y_hat = [], []
    fold_acc = []
    for test_seer in (14.0, 16.0):
        tr, te = grp != test_seer, grp == test_seer
        clf = _fit_rf(feat.loc[tr, DCOLS], y.loc[tr])
        hat = clf.predict(feat.loc[te, DCOLS])
        y_true.append(y.loc[te].to_numpy())
        y_hat.append(hat)
        fold_acc.append(float(accuracy_score(y.loc[te], hat)))
    yt, yh = np.concatenate(y_true), np.concatenate(y_hat)
    scores = _scores(yt, yh)
    scores["fold_acc"] = fold_acc
    return scores


def draw_figure(tab: pd.DataFrame) -> None:
    order = ["sim2sim", "sim2real", "lomo"]
    tab = tab.set_index("protocol").loc[order]
    fig, ax = plt.subplots(figsize=(8.0, 4.4), dpi=140)
    colors = [BLUE, ORANGE, AQUA]
    x = np.arange(len(tab))
    ax.bar(x, tab["accuracy"], color=colors, width=0.62, zorder=2)
    for i, (_, r) in enumerate(tab.iterrows()):
        ax.plot([i, i], [r["ci_low"], r["ci_high"]], color=INK, lw=1.6, zorder=3)
        ax.plot([i - 0.12, i + 0.12], [r["ci_low"], r["ci_low"]], color=INK, lw=1.6)
        ax.plot([i - 0.12, i + 0.12], [r["ci_high"], r["ci_high"]], color=INK, lw=1.6)
        ax.text(i, r["accuracy"] + 0.03, f"{r['accuracy']:.3f}", ha="center", fontsize=9)
    maj = float(tab.loc["sim2real", "majority"])
    ax.axhline(maj, color=MUTED, lw=1.2, ls="--", zorder=1)
    ax.text(2.45, maj + 0.012, f"majority {maj:.3f}", color=MUTED, fontsize=8, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            "Simulé → simulé\n(hold-out)",
            "Simulé → mesuré\n(X5)",
            "Mesuré → mesuré\n(LOMO, 5 classes)",
        ]
    )
    ax.set_ylabel("accuracy")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Le simulateur décrit-il une machine réelle ?")
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, bbox_inches="tight", dpi=140)
    print(f"figure → {FIG}")


def main():
    t0 = time.time()
    ensure_x0_readme_logs()

    probe = clip_probe()
    print("\n=== écrêtage T_evap_max = 20 °C (sain, T_sink=35) ===")
    print(probe.to_string(index=False))
    hi = safe_T_source_hi()
    print(f"T_source max sans écrêtage sain : {hi:.1f} °C  (spec demandait {T_SOURCE_SPEC[1]})")

    print("\n=== génération simulée aux conditions NIST ===")
    df = generate_sim_at_nist_conditions(T_source_hi=hi)
    n_clip = int(np.isclose(df["T_evap"], T_EVAP_CLIP, atol=1e-6).sum())
    print(f"{len(df)} lignes · T_evap == 20.0 : {n_clip}")
    if n_clip:
        raise SystemExit(f"{n_clip} cycles still sit on T_evap_max — tighten the range")
    print(df["fault_type"].value_counts().to_string())
    print(
        f"T_source [{df.T_ambient.min():.2f}, {df.T_ambient.max():.2f}]  "
        f"T_sink [{df.T_setpoint.min():.2f}, {df.T_setpoint.max():.2f}]"
    )
    SIM_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SIM_CSV, index=False)

    feat, y, grp, raw = nist_five_class()
    print(f"\n=== NIST 5 classes, T_source ≤ {T_SOURCE_NIST_MAX} °C ===")
    print(f"{len(feat)} / 7375  ·  {dict(y.value_counts())}")
    print(f"sains par machine : {dict(y[y == 'Normal'].groupby(grp).size())}")
    leak = ["EF", "CF", "LL", "UC/OC", "NF"]
    assert not any(c in feat.columns for c in leak)
    assert not any(c in raw.columns for c in leak)

    print("\n=== 1. simulé → simulé (hold-out) ===")
    sim = sim_holdout(df)
    print(
        f"acc={sim['accuracy']:.3f} [{sim['ci_low']:.3f}, {sim['ci_high']:.3f}]  "
        f"F1={sim['f1']:.3f}  val F1={sim['val_f1']:.3f}  n={sim['n']}"
    )

    print("\n=== 2. simulé → mesuré ===")
    hat = sim["clf"].predict(feat[DCOLS])
    s2r = _scores(y, hat)
    print(
        f"acc={s2r['accuracy']:.3f} [{s2r['ci_low']:.3f}, {s2r['ci_high']:.3f}]  "
        f"F1={s2r['f1']:.3f}  majority={s2r['majority']:.3f}  n={s2r['n']}"
    )

    print("\n=== 3. mesuré → mesuré (LOMO, 5 classes) ===")
    lomo = lomo_measured(feat, y, grp)
    print(
        f"acc={lomo['accuracy']:.3f} [{lomo['ci_low']:.3f}, {lomo['ci_high']:.3f}]  "
        f"F1={lomo['f1']:.3f}  plis={lomo['fold_acc'][0]:.3f}/{lomo['fold_acc'][1]:.3f}  "
        f"n={lomo['n']}"
    )

    rows = [
        {
            "protocol": "sim2sim", "reference": "simulated",
            "accuracy": sim["accuracy"], "ci_low": sim["ci_low"], "ci_high": sim["ci_high"],
            "f1": sim["f1"], "majority": sim["majority"], "n": sim["n"],
        },
        {
            "protocol": "sim2real", "reference": "measured-knn5",
            "accuracy": s2r["accuracy"], "ci_low": s2r["ci_low"], "ci_high": s2r["ci_high"],
            "f1": s2r["f1"], "majority": s2r["majority"], "n": s2r["n"],
        },
        {
            "protocol": "lomo", "reference": "measured-knn5",
            "accuracy": lomo["accuracy"], "ci_low": lomo["ci_low"], "ci_high": lomo["ci_high"],
            "f1": lomo["f1"], "majority": lomo["majority"], "n": lomo["n"],
        },
    ]
    tab = pd.DataFrame(rows)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    tab.to_csv(TABLE, index=False)
    print(f"\ntableau → {TABLE}")

    _log_block("holdout-test", "simulated", "residuals", sim, note=(
        f"95% Wilson CI [{sim['ci_low']:.3f}, {sim['ci_high']:.3f}]; "
        f"F1={sim['f1']:.3f}; NIST-domain sim; T_source≤{hi:.1f}"
    ))
    _log_block("sim2real", "measured-knn5", "residuals", s2r)
    _log_block("LOMO", "measured-knn5", "residuals", lomo, note=(
        f"95% Wilson CI [{lomo['ci_low']:.3f}, {lomo['ci_high']:.3f}]; "
        f"F1={lomo['f1']:.3f}; 5 classes; T_source≤{T_SOURCE_NIST_MAX}; "
        f"folds={lomo['fold_acc'][0]:.3f}/{lomo['fold_acc'][1]:.3f}"
    ))

    per_rows = []
    for proto, scores, ref in (
        ("holdout-test", sim, "simulated"),
        ("sim2real", s2r, "measured-knn5"),
        ("LOMO", lomo, "measured-knn5"),
    ):
        for row in scores["per_class"]:
            per_rows.append({"protocol": proto, "reference": ref, **row})
    pd.DataFrame(per_rows).to_csv(PERCLASS, index=False)
    print(f"par classe → {PERCLASS}")

    draw_figure(tab)
    print(f"durée {time.time() - t0:.0f}s")
    return tab, probe, df, feat, y, grp, sim, s2r, lomo, hi


if __name__ == "__main__":
    main()
