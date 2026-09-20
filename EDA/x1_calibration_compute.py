"""X1 calibration budget — replay EDA_NIST_calibration.ipynb and log n=10, 50."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.results import log

NIST = ROOT / "data" / "nist"
assert (NIST / "fdd_1416seer.xlsx").exists(), "place fdd_1416seer.xlsx in data/nist/"

F2C = lambda s: (s - 32) * 5 / 9
dF2K = lambda s: s * 5 / 9
PSI2BAR, BTU2W = 0.0689476, 0.293071
FAULTCOLS = {"EF": "Evap_Airflow", "CF": "Cond_Blockage", "LL": "LiquidLine", "UC/OC": "Charge"}
RES = ["superheat", "subcooling", "T_discharge", "COP", "W_od", "P_evap", "P_cond", "pressure_ratio"]
COND = ["T_source", "T_sink"]
DCOLS = [f"d_{c}" for c in RES]
ACC0, ACC_ALL = 0.318, 0.602
N_SEEDS = 20
LOG_N = (10, 50)


def fault_label(row, tol=2.0):
    active = []
    for col, name in FAULTCOLS.items():
        v = row[col]
        if pd.isna(v) or abs(v - 100) <= tol:
            continue
        if name == "Charge":
            name = "Undercharge" if v < 100 else "Overcharge"
        active.append(name)
    if not active:
        return "No_Fault"
    return active[0] if len(active) == 1 else "MULTI:" + "+".join(sorted(active))


def knn_predict(Xh_cond, Xh_res, X_cond, k=5):
    k = min(int(k), len(Xh_cond))
    tree = cKDTree(np.asarray(Xh_cond, dtype=float))
    _, idx = tree.query(np.asarray(X_cond, dtype=float), k=k)
    if idx.ndim == 1:
        idx = idx[:, None]
    return np.median(np.asarray(Xh_res)[idx], axis=1)


def load():
    df0 = pd.read_excel(NIST / "fdd_1416seer.xlsx")
    df0["fault_class"] = df0.apply(fault_label, axis=1)
    m16 = df0.Rated_SEER == 16.0
    assert (df0.loc[m16, "1710_ODSuctPort_psia"] == df0.loc[m16, "CompDisch_psia"]).all()
    X = pd.DataFrame(index=df0.index)
    X["P_evap"] = df0["1701_ODVapSV_psia"] * PSI2BAR
    X["P_cond"] = df0["CompDisch_psia"] * PSI2BAR
    X["pressure_ratio"] = X.P_cond / X.P_evap
    X["T_suction"] = F2C(df0["1608_CompSuct_TempF"])
    X["T_discharge"] = F2C(df0["1617_CompDisch_TempF"])
    X["T_evap"] = F2C(df0["CompSuct_Tsat_F"])
    X["T_cond"] = F2C(df0["CompDisch_Tsat_F"])
    X["superheat"] = dF2K(df0["CompSuct_Suph_F"])
    X["subcooling"] = dF2K(df0["ODLiqSV_Tsub_F"])
    X["Q_evap"] = df0["TOTAL Capacity (Btu/h)"] * BTU2W
    X["W_od"] = df0["OD_Xitron_Watts"]
    X["COP"] = df0["COP"]
    X["T_source"] = F2C(df0["Inlet TC Grid AVG Temp (F)"])
    X["T_sink"] = F2C(df0["OD Air AVG DB (F)"])
    y, grp = df0.fault_class, df0.Rated_SEER
    keep = grp.isin([14.0, 16.0]) & (~y.str.startswith("MULTI")) & X.notna().all(axis=1)
    return X.loc[keep].copy(), y.loc[keep].copy(), grp.loc[keep].copy()


def build_folds(X, y, grp):
    folds = {}
    for test_seer in (14.0, 16.0):
        tr = grp != test_seer
        te = grp == test_seer
        h_tr = tr & (y == "No_Fault")
        pred_tr = knn_predict(X.loc[h_tr, COND], X.loc[h_tr, RES], X.loc[tr, COND], k=5)
        Dtr = pd.DataFrame(X.loc[tr, RES].to_numpy() - pred_tr, index=X.index[tr], columns=DCOLS)
        clf = GradientBoostingClassifier(random_state=42).fit(Dtr, y.loc[tr])
        folds[test_seer] = {
            "te": te,
            "h_tr": h_tr,
            "clf": clf,
            "h_te_idx": X.index[te & (y == "No_Fault")].to_numpy(),
        }
        print(
            f"test {int(test_seer)} SEER · sains train={int(h_tr.sum())} · "
            f"sains test={len(folds[test_seer]['h_te_idx'])} · n_test={int(te.sum())}"
        )
    return folds


def evaluate(X, y, folds, n, seed):
    accs, f1s, ns = [], [], []
    rng = np.random.default_rng(seed)
    for test_seer in (14.0, 16.0):
        fold = folds[test_seer]
        te, h_tr, h_te_idx, clf = fold["te"], fold["h_tr"], fold["h_te_idx"], fold["clf"]
        te_eval = te.copy()
        if n == 0:
            src_idx = X.index[h_tr]
            k = 5
        elif n == "all":
            src_idx = h_te_idx
            k = 5
        else:
            budget = int(n)
            src_idx = rng.choice(h_te_idx, size=budget, replace=False)
            k = min(5, budget)
            te_eval.loc[src_idx] = False
        pred_te = knn_predict(X.loc[src_idx, COND], X.loc[src_idx, RES], X.loc[te, COND], k=k)
        Dte = pd.DataFrame(X.loc[te, RES].to_numpy() - pred_te, index=X.index[te], columns=DCOLS)
        eval_idx = X.index[te_eval]
        hat = clf.predict(Dte.loc[eval_idx])
        yte = y.loc[eval_idx]
        accs.append(accuracy_score(yte, hat))
        f1s.append(f1_score(yte, hat, average="macro"))
        ns.append(int(len(eval_idx)))
    return float(np.mean(accs)), float(np.mean(f1s)), int(round(float(np.mean(ns))))


def main() -> None:
    X, y, grp = load()
    folds = build_folds(X, y, grp)

    print("bound checks…", flush=True)
    acc_n0, f1_n0, _ = evaluate(X, y, folds, 0, seed=0)
    acc_all, f1_all, _ = evaluate(X, y, folds, "all", seed=0)
    print(f"  n=0    acc={acc_n0:.3f}  f1={f1_n0:.3f}   (target 0.318 / 0.290)")
    print(f"  n=all  acc={acc_all:.3f}  f1={f1_all:.3f}   (target 0.602 / 0.479)")
    if abs(acc_n0 - ACC0) >= 0.02 or abs(acc_all - ACC_ALL) >= 0.02:
        raise RuntimeError(
            f"bounds not recovered (n=0 {acc_n0:.3f}, n=all {acc_all:.3f})"
        )

    for budget in LOG_N:
        accs, f1s, ns = [], [], []
        for seed in range(N_SEEDS):
            acc, f1m, n_test = evaluate(X, y, folds, budget, seed)
            accs.append(acc)
            f1s.append(f1m)
            ns.append(n_test)
            print(f"n={budget:>3}  seed={seed:02d}  acc={acc:.3f}  f1={f1m:.3f}  n_test={n_test}", flush=True)
        acc_mean = float(np.mean(accs))
        f1_mean = float(np.mean(f1s))
        n_test = int(round(float(np.mean(ns))))
        p10, p90 = float(np.percentile(accs, 10)), float(np.percentile(accs, 90))
        note = (
            f"mean of {N_SEEDS} draws × 2 LOMO folds; calibration budget n={budget} "
            f"held out of the test set; acc p10–p90 {p10:.3f}–{p90:.3f}"
        )
        protocol = f"LOMO-calibration-n{budget}"
        print(f"{protocol} acc={acc_mean:.3f} f1={f1_mean:.3f} n_test={n_test}")
        log(
            experiment="X1",
            protocol=protocol,
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
            label="__global__",
            metric="accuracy",
            value=acc_mean,
            n=n_test,
            note=note,
        )
        log(
            experiment="X1",
            protocol=protocol,
            reference="target-machine",
            features="residuals",
            model="gradient-boosting",
            label="__global__",
            metric="f1",
            value=f1_mean,
            n=n_test,
            note=f"macro; {note}",
        )


if __name__ == "__main__":
    main()
