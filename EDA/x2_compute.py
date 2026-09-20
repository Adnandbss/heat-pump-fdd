"""X2 — does the learned model beat a sign table? Replay EDA_NIST_rules.ipynb and log."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.tree import DecisionTreeClassifier

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
LABELS = ["No_Fault", "Undercharge", "Overcharge", "Evap_Airflow", "LiquidLine", "Cond_Blockage"]


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


def sgn(x, eps=1e-4):
    return 0 if abs(x) < eps else (1 if x > 0 else -1)


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
    X, y, grp, df = X.loc[keep].copy(), y.loc[keep].copy(), grp.loc[keep].copy(), df0.loc[keep].copy()
    niveau = {
        "Cond_Blockage": 100 - df.CF,
        "Evap_Airflow": 100 - df.EF,
        "Undercharge": 100 - df["UC/OC"],
        "Overcharge": df["UC/OC"] - 100,
        "LiquidLine": 100 - df.LL,
    }
    return X, y, grp, niveau


def signs_from_train(X, y, niveau, tr):
    table = {}
    for cls in LABELS:
        if cls == "No_Fault":
            table[cls] = np.zeros(len(RES), dtype=int)
            continue
        m = ((y == cls) | (y == "No_Fault")) & tr
        lvl = niveau[cls].where(y == cls, 0.0)[m]
        vec = []
        for col in RES:
            d = pd.concat([lvl.rename("lvl"), X.loc[m, [col, "T_source", "T_sink"]]], axis=1).dropna()
            A = np.c_[np.ones(len(d)), d.lvl, d.T_source, d.T_sink]
            b = np.linalg.lstsq(A, d[col].values, rcond=None)[0][1]
            vec.append(sgn(b))
        table[cls] = np.array(vec, dtype=int)
    return table


def vote(R, table):
    sr = np.sign(R)
    scores = np.zeros((len(R), len(LABELS)))
    for i, cls in enumerate(LABELS):
        if cls == "No_Fault":
            continue
        scores[:, i] = (sr * table[cls]).sum(axis=1)
    hat_i = scores.argmax(axis=1)
    hat_i[scores.max(axis=1) <= 0] = LABELS.index("No_Fault")
    return np.array(LABELS)[hat_i]


def class_metrics(yte, hat):
    _p, _r, f1, _s = precision_recall_fscore_support(yte, hat, labels=LABELS, zero_division=0)
    return {
        "acc": accuracy_score(yte, hat),
        "f1m": f1_score(yte, hat, average="macro"),
        "f1": f1,
    }


def evaluate(folds, X, y, residual_fn, kind):
    accs, f1s, per = [], [], []
    for fold in folds:
        R = residual_fn(fold)
        if kind == "rules":
            hat = vote(R, fold["table"])
        elif kind == "gb":
            hat = fold["gb"].predict(R)
        else:
            hat = fold["dt"].predict(R)
        yte = y.loc[X.index[fold["te"]]]
        metrics = class_metrics(yte, hat)
        accs.append(metrics["acc"])
        f1s.append(metrics["f1m"])
        per.append(metrics)
    f1_cls = {lab: float(np.mean([p["f1"][i] for p in per])) for i, lab in enumerate(LABELS)}
    return float(np.mean(accs)), float(np.mean(f1s)), f1_cls


def main() -> None:
    X, y, grp, niveau = load()
    folds = []
    for test_seer in (14.0, 16.0):
        tr = grp != test_seer
        te = grp == test_seer
        h_tr = tr & (y == "No_Fault")
        h_te = te & (y == "No_Fault")
        pred_tr = knn_predict(X.loc[h_tr, COND], X.loc[h_tr, RES], X.loc[tr, COND])
        Dtr = X.loc[tr, RES].to_numpy() - pred_tr
        gb = GradientBoostingClassifier(random_state=42).fit(Dtr, y.loc[tr])
        dt = DecisionTreeClassifier(max_depth=3, random_state=42).fit(Dtr, y.loc[tr])
        table = signs_from_train(X, y, niveau, tr)
        folds.append(
            dict(tr=tr, te=te, h_tr=h_tr, h_te=h_te, gb=gb, dt=dt, table=table)
        )

    def R_cal(fold):
        pred = knn_predict(X.loc[fold["h_te"], COND], X.loc[fold["h_te"], RES], X.loc[fold["te"], COND])
        return X.loc[fold["te"], RES].to_numpy() - pred

    def R_trf(fold):
        pred = knn_predict(X.loc[fold["h_tr"], COND], X.loc[fold["h_tr"], RES], X.loc[fold["te"], COND])
        return X.loc[fold["te"], RES].to_numpy() - pred

    def R_none(fold):
        med = X.loc[fold["h_tr"], RES].median().to_numpy()
        return X.loc[fold["te"], RES].to_numpy() - med

    jobs = [
        ("gradient-boosting", "target-machine", R_cal, "gb", "calibrated kNN on the target machine"),
        ("decision-tree-d3", "target-machine", R_cal, "dt", "depth-3 tree, calibrated kNN"),
        ("rule-table", "target-machine", R_cal, "rules", "sign table, calibrated kNN"),
        ("gradient-boosting", "training-machine", R_trf, "gb", "transferred kNN from the training machine"),
        ("decision-tree-d3", "training-machine", R_trf, "dt", "depth-3 tree, transferred kNN"),
        ("rule-table", "training-machine", R_trf, "rules", "sign table, transferred kNN"),
        ("rule-table", "train-healthy-median", R_none, "rules", "sign table, train-healthy global median"),
        ("decision-tree-d3", "train-healthy-median", R_none, "dt", "depth-3 tree, train-healthy global median"),
    ]
    n = int(len(y))
    for model, reference, residual_fn, kind, note in jobs:
        acc, f1m, f1_cls = evaluate(folds, X, y, residual_fn, kind)
        print(f"{model:18s} {reference:22s} acc={acc:.3f} f1={f1m:.3f}")
        log(
            experiment="X2",
            protocol="LOMO",
            reference=reference,
            features="residuals",
            model=model,
            label="__global__",
            metric="accuracy",
            value=acc,
            n=n,
            note=note,
        )
        log(
            experiment="X2",
            protocol="LOMO",
            reference=reference,
            features="residuals",
            model=model,
            label="__global__",
            metric="f1",
            value=f1m,
            n=n,
            note=f"macro; {note}",
        )
        for label, score in f1_cls.items():
            log(
                experiment="X2",
                protocol="LOMO",
                reference=reference,
                features="residuals",
                model=model,
                label=label,
                metric="f1",
                value=score,
                n=int((y == label).sum()),
                note=note,
            )

    majority = float(y.value_counts().max() / len(y))
    log(
        experiment="X2",
        protocol="majority-class",
        reference="none",
        features="",
        model="baseline",
        label="__global__",
        metric="accuracy",
        value=majority,
        n=n,
        note="most frequent class in the usable NIST rows",
    )
    print(f"majority {majority:.3f}")


if __name__ == "__main__":
    main()
