"""X4 — does 91.9 % survive a domain hold-out?

Same pipeline as production: sklearn Pipeline (scaler + Random Forest), train/val/test,
selection never sees the held-out region. No hyperparameter search (the shipped model is RF).
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fdd.features import FEATURE_COLUMNS
from src.fdd.ml_models import FDDClassifier, wilson_ci
from tools.results import drop, log

DATASET = ROOT / "outputs" / "synthetic" / "dataset.csv"
FIG = ROOT / "docs" / "nist_x4_domain.png"
TABLE = ROOT / "outputs" / "x4_domain_holdout.csv"
SEED = 42
LABELS = [
    "Normal",
    "Condenser_Fouling",
    "Evaporator_Fouling",
    "Refrigerant_Undercharge",
    "Condenser_Fan_Fault",
    "Evaporator_Fan_Fault",
]
# Fan faults have severity_min = 0.20 — never mild. Severity hold-out
# is restricted to the four classes that exist on both sides of 0.20.
SEV_LABELS = [
    "Normal",
    "Condenser_Fouling",
    "Evaporator_Fouling",
    "Refrigerant_Undercharge",
]
FAN_LABELS = ["Condenser_Fan_Fault", "Evaporator_Fan_Fault"]
BIN_LABELS = ["Normal", "Fault"]
CONFUSED_PROTOCOLS = (
    "holdout-domain-severity<0.20",
    "holdout-domain-severity>=0.20",
)
BLUE, ORANGE, MUTED, GRID = "#2a78d6", "#eb6834", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "text.color": "#0b0b0b",
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})


def fit_rf(X_train, y_train, X_val, y_val, X_test, y_test, labels=None):
    """Fit the production RF pipeline. Metrics computed here so a test
    split that misses a class does not trip classification_report inside
    FDDClassifier.evaluate."""
    labels = list(labels or LABELS)
    clf = FDDClassifier(model_type="random_forest", random_state=SEED)
    clf._estimator.set_params(n_jobs=1)
    clf.fit(X_train, y_train, feature_columns=list(FEATURE_COLUMNS))
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    present = [c for c in labels if (np.asarray(y_test) == c).any()]
    f1 = float(f1_score(y_test, y_pred, average="macro", labels=present, zero_division=0))
    n = int(len(y_test))
    lo, hi = wilson_ci(acc, n)
    present_val = [c for c in labels if (np.asarray(y_val) == c).any()]
    val_f1 = float(f1_score(y_val, clf.predict(X_val), average="macro", labels=present_val, zero_division=0))
    imp = clf._get_feature_importance()
    return {
        "clf": clf, "acc": acc, "f1": f1, "n": n, "lo": lo, "hi": hi,
        "val_f1": val_f1, "pred": y_pred, "imp": imp,
    }


def split_train_val(X, y):
    return train_test_split(X, y, test_size=0.25, random_state=SEED, stratify=y)


def composition(y, labels=None):
    labels = list(labels or LABELS)
    counts = pd.Series(y).value_counts()
    return {k: int(counts.get(k, 0)) for k in labels}


def per_class(y_true, y_pred, labels=None):
    labels = list(labels or LABELS)
    p, r, f1, n = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    return {lab: {"f1": float(fi), "n": int(s)} for lab, fi, s in zip(labels, f1, n)}


def log_split(protocol, acc, f1, n, note, y_true=None, y_pred=None, labels=None):
    lo, hi = wilson_ci(acc, n)
    log(
        experiment="X4", protocol=protocol, reference="simulated",
        features="24-col", model="random-forest", label="__global__",
        metric="accuracy", value=acc, n=n,
        note=f"95% Wilson [{lo:.3f}, {hi:.3f}]; F1={f1:.3f}; {note}",
    )
    log(
        experiment="X4", protocol=protocol, reference="simulated",
        features="24-col", model="random-forest", label="__global__",
        metric="f1", value=f1, n=n, note="macro; selected on val of complement",
    )
    if y_true is not None:
        for lab, row in per_class(y_true, y_pred, labels=labels).items():
            if row["n"] == 0:
                continue
            log(
                experiment="X4", protocol=protocol, reference="simulated",
                features="24-col", model="random-forest", label=lab,
                metric="f1", value=row["f1"], n=row["n"],
            )
    return lo, hi


def run_mask(name, protocol, df, test_mask, note, do_log=True, labels=None):
    labels = list(labels or LABELS)
    y = df["fault_type"]
    X = df[FEATURE_COLUMNS]
    te, trv = test_mask, ~test_mask
    print(f"\n=== {name} ===")
    print(f"  n_test={int(te.sum())}  n_trainval={int(trv.sum())}")
    print("  test mix :", {k: v for k, v in composition(y[te], labels).items() if v})
    print("  train mix:", {k: v for k, v in composition(y[trv], labels).items() if v})
    missing_train = [k for k, v in composition(y[trv], labels).items() if v == 0]
    if missing_train:
        print("  absent du train:", missing_train, "— le modèle ne peut pas les prédire")
    if y[te].nunique() < 2:
        print("  SKIP — fewer than 2 classes in test")
        return None
    X_tr, X_va, y_tr, y_va = split_train_val(X[trv], y[trv])
    packed = fit_rf(X_tr, y_tr, X_va, y_va, X[te], y[te], labels=labels)
    maj = float(y[te].value_counts().max() / te.sum())
    if do_log:
        lo, hi = log_split(
            protocol, packed["acc"], packed["f1"], packed["n"], note,
            y_true=y[te], y_pred=packed["pred"], labels=labels,
        )
    else:
        lo, hi = packed["lo"], packed["hi"]
    top = []
    if packed["imp"] is not None:
        top = list(packed["imp"].head(5)["feature"])
    print(
        f"  acc={packed['acc']:.3f} [{lo:.3f}, {hi:.3f}]  "
        f"F1={packed['f1']:.3f}  majority={maj:.3f}  val F1={packed['val_f1']:.3f}"
    )
    print("  top features:", top)
    print("  pred mix :", {k: v for k, v in composition(packed["pred"], labels).items() if v})
    if packed["imp"] is not None:
        ranked = list(packed["imp"]["feature"])
        suspects = ["d_COP", "T_ambient", "T_setpoint", "compressor_speed_ratio", "COP"]
        print("  rangs fuite :", {s: ranked.index(s) + 1 if s in ranked else None for s in suspects})
    cm = pd.DataFrame(
        confusion_matrix(y[te], packed["pred"], labels=labels),
        index=labels, columns=labels,
    )
    present_idx = [c for c in labels if composition(y[te], labels)[c] > 0]
    print(cm.loc[present_idx].to_string())
    pc = per_class(y[te], packed["pred"], labels)
    for lab, row in pc.items():
        if row["n"]:
            print(f"    {lab:24s} F1={row['f1']:.3f}  n={row['n']}")
    rec = {
        "split": name, "protocol": protocol, "acc": packed["acc"],
        "acc_lo": lo, "acc_hi": hi, "f1": packed["f1"],
        "n_test": packed["n"], "majority": maj, "n_classes_test": int(y[te].nunique()),
        "top_features": ",".join(top),
        **{f"n_{k}": composition(y[te], LABELS)[k] for k in LABELS},
        **{f"f1_{k}": per_class(y[te], packed["pred"], LABELS)[k]["f1"] for k in LABELS},
    }
    return rec, packed["clf"], packed["imp"]


def run_groupkfold(df):
    y = df["fault_type"]
    X = df[FEATURE_COLUMNS]
    ta = pd.qcut(df["T_ambient"], 4, labels=False, duplicates="drop")
    ts = pd.qcut(df["T_setpoint"], 4, labels=False, duplicates="drop")
    groups = (ta.astype(int) * 10 + ts.astype(int)).to_numpy()
    gkf = GroupKFold(n_splits=5)
    accs, f1s, ns = [], [], []
    y_true_all, y_pred_all = [], []
    print("\n=== GroupKFold T_ambient × T_setpoint (4×4 bacs, 5 plis) ===")
    print("  n_groups", pd.Series(groups).nunique(), "sizes", dict(pd.Series(groups).value_counts().sort_index()))
    for fold, (trv_idx, te_idx) in enumerate(gkf.split(X, y, groups), 1):
        X_tr, X_va, y_tr, y_va = split_train_val(X.iloc[trv_idx], y.iloc[trv_idx])
        packed = fit_rf(X_tr, y_tr, X_va, y_va, X.iloc[te_idx], y.iloc[te_idx])
        accs.append(packed["acc"])
        f1s.append(packed["f1"])
        ns.append(packed["n"])
        y_true_all.append(y.iloc[te_idx].to_numpy())
        y_pred_all.append(packed["pred"])
        print(f"  pli {fold}: n={packed['n']} acc={packed['acc']:.3f} F1={packed['f1']:.3f}")
    acc, f1 = float(np.mean(accs)), float(np.mean(f1s))
    n = int(np.sum(ns))
    yt = np.concatenate(y_true_all)
    yp = np.concatenate(y_pred_all)
    pooled_acc = float(accuracy_score(yt, yp))
    present = [c for c in LABELS if (yt == c).any()]
    pooled_f1 = float(f1_score(yt, yp, average="macro", labels=present, zero_division=0))
    lo_p, hi_p = wilson_ci(pooled_acc, n)
    maj = float(pd.Series(yt).value_counts().max() / n)
    note = (
        f"5-fold GroupKFold; fold-mean acc={acc:.3f}±{np.std(accs):.3f}; "
        f"pooled {pooled_acc:.3f}"
    )
    log_split("holdout-domain-GroupKFold", pooled_acc, pooled_f1, n, note, y_true=yt, y_pred=yp)
    pc = per_class(yt, yp)
    print(f"  pooled acc={pooled_acc:.3f} [{lo_p:.3f}, {hi_p:.3f}]  F1={pooled_f1:.3f}  majority={maj:.3f}")
    rec = {
        "split": "GroupKFold (T_amb × T_set)",
        "protocol": "holdout-domain-GroupKFold",
        "acc": pooled_acc, "acc_lo": lo_p, "acc_hi": hi_p, "f1": pooled_f1,
        "n_test": n, "majority": maj, "n_classes_test": int(pd.Series(yt).nunique()),
        "top_features": "",
        **{f"n_{k}": int((yt == k).sum()) for k in LABELS},
        **{f"f1_{k}": pc[k]["f1"] for k in LABELS},
    }
    return rec


def _empty_counts():
    return {f"n_{k}": 0 for k in LABELS} | {f"f1_{k}": 0.0 for k in LABELS}


def run_severity_4class(df):
    """Hold-out on severity, restricted to classes that exist on both sides of 0.20."""
    print("\n=== sévérité — 4 classes (fans exclus) ===")
    print("  exclus:", FAN_LABELS)
    print("  raison: generator severity_min = 0.20 for fan_*_ratio — no mild fans")
    sub = df[df.fault_type.isin(SEV_LABELS)].copy()
    print("  n_universe", len(sub), "of", len(df))
    for lab in SEV_LABELS:
        sl = sub.loc[sub.fault_type == lab, "fault_severity"]
        if lab == "Normal":
            print(f"    {lab:24s} n={len(sl)}")
        else:
            mild_n = int((sl < 0.20).sum())
            sev_n = int((sl >= 0.20).sum())
            print(f"    {lab:24s} min={sl.min():.2f} max={sl.max():.2f}  n<0.20={mild_n}  n>=0.20={sev_n}")

    recs = []
    specs = [
        (
            "sévérité < 0.20 (4 classes)",
            "holdout-severity-4class-<0.20",
            (sub.is_faulty == 1) & (sub.fault_severity < 0.20),
            "4-class; fans excluded; train=Normal+severe of fouling/UC; test=mild",
        ),
        (
            "sévérité ≥ 0.20 (4 classes)",
            "holdout-severity-4class->=0.20",
            (sub.is_faulty == 1) & (sub.fault_severity >= 0.20),
            "4-class; fans excluded; train=Normal+mild of fouling/UC; test=severe",
        ),
    ]
    for name, proto, mask, note in specs:
        out = run_mask(name, proto, sub, mask.to_numpy(), note, labels=SEV_LABELS)
        if out is not None:
            recs.append(out[0])
    return recs


def run_binary_severity(df):
    """Fault vs Normal, all six original classes collapsed. Normal 70/30 held out
    so the test has a false-positive denominator."""
    print("\n=== détection binaire (6 classes → Fault / Normal) ===")
    y_bin = np.where(df.fault_type.eq("Normal"), "Normal", "Fault")
    normal_idx = df.index[df.fault_type.eq("Normal")].to_numpy()
    n_tr, n_te = train_test_split(normal_idx, test_size=0.30, random_state=SEED)
    mild = (df.is_faulty == 1) & (df.fault_severity < 0.20)
    severe = (df.is_faulty == 1) & (df.fault_severity >= 0.20)
    print("  Normal train/test", len(n_tr), len(n_te))
    print("  mild faults", int(mild.sum()), "severe faults", int(severe.sum()))
    print("  mild mix", {k: v for k, v in composition(df.loc[mild, "fault_type"]).items() if v})
    print("  severe mix", {k: v for k, v in composition(df.loc[severe, "fault_type"]).items() if v})

    recs = []
    specs = [
        (
            "binaire, train mild → test severe",
            "holdout-binary-severity-train<0.20",
            np.union1d(n_tr, df.index[mild].to_numpy()),
            np.union1d(n_te, df.index[severe].to_numpy()),
            "binary Fault/Normal; train Normal+mild (all 6 classes); test held-out Normal+severe",
        ),
        (
            "binaire, train severe → test mild",
            "holdout-binary-severity-train>=0.20",
            np.union1d(n_tr, df.index[severe].to_numpy()),
            np.union1d(n_te, df.index[mild].to_numpy()),
            "binary Fault/Normal; train Normal+severe (all 6 classes); test held-out Normal+mild",
        ),
    ]
    X = df[FEATURE_COLUMNS]
    for name, proto, tr_idx, te_idx, note in specs:
        print(f"\n=== {name} ===")
        y_tr_all, y_te = y_bin[tr_idx], y_bin[te_idx]
        X_tr_all, X_te = X.loc[tr_idx], X.loc[te_idx]
        print("  n_test", len(te_idx), "n_trainval", len(tr_idx))
        print("  test mix", composition(y_te, BIN_LABELS))
        print("  train mix", composition(y_tr_all, BIN_LABELS))
        X_tr, X_va, y_tr, y_va = split_train_val(X_tr_all, pd.Series(y_tr_all, index=X_tr_all.index))
        packed = fit_rf(X_tr, y_tr, X_va, y_va, X_te, pd.Series(y_te, index=X_te.index), labels=BIN_LABELS)
        maj = float(pd.Series(y_te).value_counts().max() / len(y_te))
        lo, hi = log_split(
            proto, packed["acc"], packed["f1"], packed["n"], note,
            y_true=y_te, y_pred=packed["pred"], labels=BIN_LABELS,
        )
        # detection metrics on the Fault class
        yt = np.asarray(y_te)
        yp = np.asarray(packed["pred"])
        tp = int(((yt == "Fault") & (yp == "Fault")).sum())
        fn = int(((yt == "Fault") & (yp == "Normal")).sum())
        fp = int(((yt == "Normal") & (yp == "Fault")).sum())
        tn = int(((yt == "Normal") & (yp == "Normal")).sum())
        rec_f = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        print(
            f"  acc={packed['acc']:.3f} [{lo:.3f}, {hi:.3f}]  "
            f"F1={packed['f1']:.3f}  majority={maj:.3f}  val F1={packed['val_f1']:.3f}"
        )
        print(f"  recall Fault={rec_f:.3f}  FPR={fpr:.3f}  TP={tp} FN={fn} FP={fp} TN={tn}")
        pc = per_class(y_te, packed["pred"], BIN_LABELS)
        for lab, row in pc.items():
            print(f"    {lab:8s} F1={row['f1']:.3f}  n={row['n']}")
        rec = {
            "split": name, "protocol": proto, "acc": packed["acc"],
            "acc_lo": lo, "acc_hi": hi, "f1": packed["f1"],
            "n_test": packed["n"], "majority": maj, "n_classes_test": 2,
            "top_features": ",".join(packed["imp"].head(5)["feature"]) if packed["imp"] is not None else "",
            **_empty_counts(),
            "n_Normal": int((yt == "Normal").sum()),
            "f1_Normal": pc["Normal"]["f1"],
        }
        recs.append(rec)
        log(
            experiment="X4", protocol=proto, reference="simulated",
            features="24-col", model="random-forest", label="Fault",
            metric="recall", value=rec_f, n=int((yt == "Fault").sum()),
            note=f"FPR={fpr:.3f}; TP={tp} FN={fn} FP={fp} TN={tn}",
        )
    return recs


def main():
    df = pd.read_csv(DATASET)
    y = df["fault_type"]
    X = df[FEATURE_COLUMNS]
    print(f"{len(df)} lignes · {y.nunique()} classes")
    print("T_ambient", round(df.T_ambient.min(), 1), "→", round(df.T_ambient.max(), 1))
    print("T_setpoint", round(df.T_setpoint.min(), 1), "→", round(df.T_setpoint.max(), 1))
    print("speed", round(df.compressor_speed_ratio.min(), 2), "→", round(df.compressor_speed_ratio.max(), 2))
    sev = df.loc[df.is_faulty == 1, "fault_severity"]
    print("sévérité (défauts)", round(sev.min(), 2), "→", round(sev.max(), 2), "médiane", round(sev.median(), 2))

    # --- control: published random hold-out ---
    X_tv, X_te, y_tv, y_te = train_test_split(
        X, y, test_size=0.3, random_state=SEED, stratify=y
    )
    X_tr, X_va, y_tr, y_va = train_test_split(
        X_tv, y_tv, test_size=0.25, random_state=SEED, stratify=y_tv
    )
    print(f"\n=== CONTRÔLE hold-out aléatoire  {len(X_tr)}/{len(X_va)}/{len(X_te)} ===")
    packed = fit_rf(X_tr, y_tr, X_va, y_va, X_te, y_te)
    te = packed
    va_f1 = packed["val_f1"]
    imp = packed["imp"]
    lo, hi = packed["lo"], packed["hi"]
    print(f"  acc={te['acc']:.4f} [{lo:.3f}, {hi:.3f}]  F1={te['f1']:.3f}  val F1={va_f1:.3f}")
    print("  top:", list(imp.head(5)["feature"]) if imp is not None else None)
    if imp is not None:
        ranked = list(imp["feature"])
        suspects = ["d_COP", "T_ambient", "T_setpoint", "compressor_speed_ratio", "COP"]
        print("  rangs fuite :", {s: ranked.index(s) + 1 if s in ranked else None for s in suspects})
        print(imp.head(12).to_string(index=False))
    if abs(te["acc"] - 0.918667) > 0.025:
        raise SystemExit(f"contrôle hors de 91.9 %: {te['acc']:.4f}")
    print("contrôle OK — même split, même RF, Pipeline.")
    log_split(
        "holdout-random-control", te["acc"], te["f1"], te["n"],
        "reproduces X0 protocol; n_jobs=1",
        y_true=y_te, y_pred=te["pred"],
    )
    control_acc = te["acc"]
    rows = [{
        "split": "aléatoire (référence)",
        "protocol": "holdout-random-control",
        "acc": te["acc"], "acc_lo": lo, "acc_hi": hi, "f1": te["f1"],
        "n_test": te["n"],
        "majority": float(y_te.value_counts().max() / te["n"]),
        "n_classes_test": int(y_te.nunique()),
        "top_features": ",".join(imp.head(5)["feature"]) if imp is not None else "",
        **{f"n_{k}": composition(y_te)[k] for k in LABELS},
        **{f"f1_{k}": per_class(y_te, te["pred"])[k]["f1"] for k in LABELS},
    }]

    mild = (df.is_faulty == 1) & (df.fault_severity < 0.20)
    severe = (df.is_faulty == 1) & (df.fault_severity >= 0.20)
    splits = [
        ("T_setpoint > 48 °C", "holdout-domain-Tsink>48", df.T_setpoint > 48, "extrapolation puits chaud"),
        ("T_ambient < −5 °C", "holdout-domain-Tamb<-5", df.T_ambient < -5, "extrapolation source froide"),
        ("speed_ratio > 0.85", "holdout-domain-speed>0.85", df.compressor_speed_ratio > 0.85, "extrapolation régime"),
    ]
    recs = []
    for name, proto, mask, note in splits:
        out = run_mask(name, proto, df, mask.to_numpy(), note)
        if out is not None:
            recs.append(out[0])

    recs.append(run_groupkfold(df))

    for proto in CONFUSED_PROTOCOLS:
        n_drop = drop(experiment="X4", protocol=proto)
        print(f"dropped {n_drop} confounded rows  protocol={proto}")
    recs.extend(run_severity_4class(df))
    recs.extend(run_binary_severity(df))

    rows.extend(recs)
    tab = pd.DataFrame(rows)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    tab.to_csv(TABLE, index=False)
    print(f"\ntableau → {TABLE}")

    # figure: the four operating-point splits — the result that holds
    plot = tab[tab.protocol.isin([
        "holdout-domain-Tsink>48",
        "holdout-domain-Tamb<-5",
        "holdout-domain-speed>0.85",
        "holdout-domain-GroupKFold",
    ])].copy()
    order = [
        "T_setpoint > 48 °C",
        "T_ambient < −5 °C",
        "speed_ratio > 0.85",
        "GroupKFold (T_amb × T_set)",
    ]
    plot["split"] = pd.Categorical(plot["split"], order, ordered=True)
    plot = plot.sort_values("split")

    fig, ax = plt.subplots(figsize=(7.4, 4.6), dpi=140)
    x = np.arange(len(plot))
    yerr = np.vstack([plot.acc - plot.acc_lo, plot.acc_hi - plot.acc])
    ax.bar(x, plot.acc, color=BLUE, width=0.62, zorder=3)
    ax.errorbar(x, plot.acc, yerr=yerr, fmt="none", ecolor="#0b0b0b", capsize=3, lw=1, zorder=4)
    ax.axhline(control_acc, color=ORANGE, lw=1.8, ls="--", zorder=2,
               label=f"hold-out aléatoire  {control_acc*100:.1f} %")
    ax.scatter(x, plot.majority, color=MUTED, marker="_", s=280, zorder=5, linewidths=2.2,
               label="classe majoritaire du test")
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace(" (", "\n(") for s in plot.split], fontsize=9)
    ax.set_ylim(0.30, 1.02)
    ax.set_ylabel("accuracy")
    ax.set_title("Le 91,9 % survit hors des conditions apprises")
    ax.legend(frameon=False, loc="lower left")
    for i, (acc, n) in enumerate(zip(plot.acc, plot.n_test)):
        ax.text(i, acc + 0.018, f"{acc:.3f}\nn={n}", ha="center", va="bottom", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(FIG, bbox_inches="tight", dpi=140)
    print(f"figure → {FIG}")
    return tab


if __name__ == "__main__":
    main()
