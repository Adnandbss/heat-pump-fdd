"""X3 compute — run from repo root, then the notebook embeds the same protocol.

Classifier is frozen per fold (train residuals = knn5-median on train-healthy).
Only the *test-time* healthy estimator varies. That is the published 0.602 protocol.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from sklearn.ensemble import GradientBoostingClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "requirements.txt").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.results import log

NIST = ROOT / "data" / "nist"
FIG = ROOT / "docs" / "nist_x3_dmin.png"
TABLE = ROOT / "outputs" / "x3_estimator_dmin.csv"
assert (NIST / "fdd_1416seer.xlsx").exists()

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
})

F2C = lambda s: (s - 32) * 5 / 9
dF2K = lambda s: s * 5 / 9
PSI2BAR, BTU2W = 0.0689476, 0.293071
FAULTCOLS = {"EF": "Evap_Airflow", "CF": "Cond_Blockage", "LL": "LiquidLine", "UC/OC": "Charge"}
DMINS = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
KS = (1, 3, 5, 10, 20)
LABELS = ["No_Fault", "Undercharge", "Overcharge", "Evap_Airflow", "LiquidLine", "Cond_Blockage"]
RES = ["superheat", "subcooling", "T_discharge", "COP", "W_od", "P_evap", "P_cond", "pressure_ratio"]
COND2 = ["T_source", "T_sink"]
COND3 = ["T_source", "T_sink", "T_dew"]


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
    X["T_dew"] = F2C(df0["1703_VDC_KahnDewTempF"])
    leak = ["EF", "CF", "LL", "UC/OC", "NF"]
    assert not any(c in X.columns for c in leak)
    y, grp = df0.fault_class, df0.Rated_SEER
    keep = grp.isin([14.0, 16.0]) & (~y.str.startswith("MULTI")) & X[RES + COND3].notna().all(axis=1)
    return X.loc[keep].copy(), y.loc[keep].copy(), grp.loc[keep].copy()


def knn_estimate(cond_h, res_h, cond_q, k=5, dmin=0.0, agg="median", weighted=False):
    cond_h = np.asarray(cond_h, dtype=float)
    res_h = np.asarray(res_h, dtype=float)
    cond_q = np.asarray(cond_q, dtype=float)
    n_h = len(cond_h)
    n_q, n_r = len(cond_q), res_h.shape[1]
    out = np.empty((n_q, n_r))
    tree = cKDTree(cond_h)
    kq = n_h if (dmin > 0 or weighted) else min(int(k), n_h)
    dist, idx = tree.query(cond_q, k=kq)
    if kq == 1:
        dist, idx = dist[:, None], idx[:, None]
    k = min(int(k), n_h)
    for i in range(n_q):
        d, j = dist[i], idx[i]
        ok = d >= (dmin - 1e-15)
        if not np.any(ok):
            ok = np.ones(len(d), dtype=bool)
        j, d = j[ok], d[ok]
        take = min(k, len(j))
        j, d = j[:take], d[:take]
        vals = res_h[j]
        if weighted:
            w = 1.0 / np.maximum(d, 1e-6)
            w = w / w.sum()
            out[i] = vals.T @ w
        elif agg == "median":
            out[i] = np.median(vals, axis=0)
        else:
            out[i] = np.mean(vals, axis=0)
    return out


def global_estimate(cond_h, res_h, cond_q, dmin=0.0, agg="median"):
    cond_h = np.asarray(cond_h, dtype=float)
    res_h = np.asarray(res_h, dtype=float)
    cond_q = np.asarray(cond_q, dtype=float)
    if dmin <= 0:
        vec = np.median(res_h, axis=0) if agg == "median" else np.mean(res_h, axis=0)
        return np.broadcast_to(vec, (len(cond_q), res_h.shape[1])).copy()
    tree = cKDTree(cond_h)
    dist, idx = tree.query(cond_q, k=len(cond_h))
    if dist.ndim == 1:
        dist, idx = dist[:, None], idx[:, None]
    out = np.empty((len(cond_q), res_h.shape[1]))
    for i in range(len(cond_q)):
        ok = dist[i] >= (dmin - 1e-15)
        sel = idx[i][ok]
        if len(sel) == 0:
            sel = idx[i]
        vals = res_h[sel]
        out[i] = np.median(vals, axis=0) if agg == "median" else np.mean(vals, axis=0)
    return out


def _poly(kind, dew):
    if kind == "lin":
        return LinearRegression()
    if kind == "poly2":
        return Pipeline([
            ("poly", PolynomialFeatures(2, include_bias=True)),
            ("lin", LinearRegression()),
        ])
    return Pipeline([
        ("poly", PolynomialFeatures(2, include_bias=True)),
        ("ridge", Ridge(alpha=1.0)),
    ])


def fitted_estimate(cond_h, res_h, cond_q, dmin=0.0, kind="lin"):
    cond_h = np.asarray(cond_h, dtype=float)
    res_h = np.asarray(res_h, dtype=float)
    cond_q = np.asarray(cond_q, dtype=float)
    if dmin <= 0:
        est = _poly(kind, False)
        est.fit(cond_h, res_h)
        return est.predict(cond_q)
    tree = cKDTree(cond_h)
    dist, idx = tree.query(cond_q, k=len(cond_h))
    if dist.ndim == 1:
        dist, idx = dist[:, None], idx[:, None]
    out = np.empty((len(cond_q), res_h.shape[1]))
    min_n = cond_h.shape[1] + 2
    for i in range(len(cond_q)):
        ok = dist[i] >= (dmin - 1e-15)
        sel = idx[i][ok]
        if len(sel) < min_n:
            sel = idx[i]
        est = _poly(kind, False)
        est.fit(cond_h[sel], res_h[sel])
        out[i] = est.predict(cond_q[i:i + 1])[0]
    return out


def rf_estimate(cond_h, res_h, cond_q):
    est = RandomForestRegressor(
        n_estimators=80, max_depth=8, min_samples_leaf=3,
        random_state=42, n_jobs=1,
    )
    est.fit(np.asarray(cond_h, float), np.asarray(res_h, float))
    return est.predict(np.asarray(cond_q, float))


def fold_mean_scores(y_true_folds, y_hat_folds):
    accs, f1s = [], []
    for yt, yh in zip(y_true_folds, y_hat_folds):
        accs.append(accuracy_score(yt, yh))
        f1s.append(f1_score(yt, yh, average="macro", zero_division=0))
    return float(np.mean(accs)), float(np.mean(f1s)), accs, f1s


def healthy_mae(cond_h, res_h, cond_q, res_q, predict_fn):
    """MAE of reconstructed healthy sensors. Query points are the healthy tests.
    Self is excluded by dmin=1e-9 when the estimator is a lookup."""
    pred = predict_fn(cond_h, res_h, cond_q)
    return float(np.mean(np.abs(np.asarray(res_q, float) - pred)))


def main():
    t0 = time.time()
    X, y, grp = load()
    print(f"{len(X)} lignes · {y.nunique()} classes")
    print(dict(y.value_counts()))
    print("sains par machine :", dict(y[y == "No_Fault"].groupby(grp).size()))

    # replica structure, within machine
    d_euc, d_cheb, n_fault = [], [], 0
    for seer in (14.0, 16.0):
        h = X.loc[(grp == seer) & (y == "No_Fault"), COND2].to_numpy()
        f = X.loc[(grp == seer) & (y != "No_Fault"), COND2].to_numpy()
        de, _ = cKDTree(h).query(f, k=1)
        dc = np.max(np.abs(f[:, None, :] - h[None, :, :]), axis=2).min(axis=1)
        d_euc.append(de)
        d_cheb.append(dc)
        n_fault += len(f)
    d_euc, d_cheb = np.concatenate(d_euc), np.concatenate(d_cheb)
    print(f"essais défaillants: {n_fault}")
    print(f"  euclidienne  d<0.1 °C: {(d_euc < 0.1).mean():.3f}   d<0.5: {(d_euc < 0.5).mean():.3f}")
    print(f"  Chebyshev    d<0.1 °C: {(d_cheb < 0.1).mean():.3f}   d<0.5: {(d_cheb < 0.5).mean():.3f}")
    print("dmin est euclidien — même métrique que le kNN.")

    # freeze classifier: train residuals = published knn5-median on TRAIN healthy
    folds = {}
    for test_seer in (14.0, 16.0):
        tr = grp != test_seer
        te = grp == test_seer
        h_tr = tr & (y == "No_Fault")
        h_te = te & (y == "No_Fault")
        pred_tr = knn_estimate(X.loc[h_tr, COND2], X.loc[h_tr, RES], X.loc[tr, COND2], k=5, agg="median")
        Dtr = X.loc[tr, RES].to_numpy() - pred_tr
        clf = GradientBoostingClassifier(random_state=42).fit(Dtr, y.loc[tr])
        folds[test_seer] = dict(tr=tr, te=te, h_tr=h_tr, h_te=h_te, clf=clf)
        print(
            f"test {int(test_seer)} SEER · sains train={int(h_tr.sum())} · "
            f"sains test={int(h_te.sum())} · n_test={int(te.sum())}"
        )

    def evaluate(predict_fn, cond_cols):
        y_true_f, y_hat_f = [], []
        mae_h = []
        for test_seer, f in folds.items():
            h, te, clf = f["h_te"], f["te"], f["clf"]
            pred = predict_fn(X.loc[h, cond_cols], X.loc[h, RES], X.loc[te, cond_cols])
            Dte = X.loc[te, RES].to_numpy() - pred
            hat = clf.predict(Dte)
            y_true_f.append(y.loc[te].to_numpy())
            y_hat_f.append(hat)
            # reconstruction error on healthy test rows (includes self at dmin=0)
            pred_h = predict_fn(X.loc[h, cond_cols], X.loc[h, RES], X.loc[h, cond_cols])
            mae_h.append(float(np.mean(np.abs(X.loc[h, RES].to_numpy() - pred_h))))
        acc, f1, accs, f1s = fold_mean_scores(y_true_f, y_hat_f)
        yt = np.concatenate(y_true_f)
        yh = np.concatenate(y_hat_f)
        return {
            "acc": acc, "f1": f1, "accs": accs, "f1s": f1s,
            "mae_healthy": float(np.mean(mae_h)),
            "y_true": yt, "y_hat": yh, "n": int(len(yt)),
        }

    # --- control: published knn5 median ---
    ctrl = evaluate(
        lambda ch, rh, cq: knn_estimate(ch, rh, cq, k=5, dmin=0.0, agg="median"),
        COND2,
    )
    print(
        f"\nCONTRÔLE knn5-median (T,T) dmin=0 : acc={ctrl['acc']:.3f}  F1={ctrl['f1']:.3f}  "
        f"plis={ctrl['accs'][0]:.3f}/{ctrl['accs'][1]:.3f}"
    )
    if abs(ctrl["acc"] - 0.602) > 0.008:
        raise SystemExit(f"contrôle raté: {ctrl['acc']:.4f} (attendu ~0.602)")
    print("contrôle OK — protocole identique au 0,602 publié.")

    # sklearn KNeighborsRegressor trap (mean, not median)
    def knn_sklearn_mean(ch, rh, cq, k=5):
        est = KNeighborsRegressor(n_neighbors=min(k, len(ch)))
        est.fit(np.asarray(ch, float), np.asarray(rh, float))
        return est.predict(np.asarray(cq, float))

    trap = evaluate(lambda ch, rh, cq: knn_sklearn_mean(ch, rh, cq, 5), COND2)
    print(f"piège KNeighborsRegressor (moyenne k=5) : acc={trap['acc']:.3f}  F1={trap['f1']:.3f}")
    log(
        experiment="X3", protocol="LOMO", reference="sklearn-KNeighborsRegressor-mean-k5-TT-dmin0",
        features="residuals", model="gradient-boosting",
        metric="accuracy", value=trap["acc"], n=trap["n"],
        note="sklearn mean, not project median; trap control",
    )

    rows = []
    stored = {}

    def run_one(name, cond_cols, predict_fn, dmin):
        r = evaluate(predict_fn, cond_cols)
        dew = "TTdew" if cond_cols is COND3 else "TT"
        rec = {
            "estimator": name, "dew": dew, "dmin": dmin,
            "acc": r["acc"], "f1": r["f1"],
            "acc_14": r["accs"][0], "acc_16": r["accs"][1],
            "mae_healthy": r["mae_healthy"], "n": r["n"],
        }
        rows.append(rec)
        key = (name, dew, dmin)
        stored[key] = r
        ref = f"{name}-{dew}-dmin{dmin:g}"
        log(
            experiment="X3", protocol="LOMO", reference=ref,
            features="residuals", model="gradient-boosting",
            metric="accuracy", value=r["acc"], n=r["n"],
            note=f"fold-mean; F1={r['f1']:.3f}; mae_h={r['mae_healthy']:.4f}",
        )
        log(
            experiment="X3", protocol="LOMO", reference=ref,
            features="residuals", model="gradient-boosting",
            metric="f1", value=r["f1"], n=r["n"],
            note="macro; mean of two LOMO folds",
        )
        print(
            f"  {ref:42s}  acc={r['acc']:.3f}  F1={r['f1']:.3f}  "
            f"mae_h={r['mae_healthy']:.3f}"
        )
        return r

    print("\n=== kNN ===")
    for dew, cols in (("TT", COND2), ("TTdew", COND3)):
        for k in KS:
            for agg in ("median", "mean"):
                for weighted in (False, True):
                    if weighted and agg == "median":
                        continue
                    wtag = "dist" if weighted else "unif"
                    name = f"knn-k{k}-{agg}-{wtag}"
                    for dmin in DMINS:
                        run_one(
                            name, cols,
                            lambda ch, rh, cq, k=k, dmin=dmin, agg=agg, weighted=weighted:
                                knn_estimate(ch, rh, cq, k=k, dmin=dmin, agg=agg, weighted=weighted),
                            dmin,
                        )

    print("\n=== planchers globaux ===")
    for dew, cols in (("TT", COND2), ("TTdew", COND3)):
        for agg in ("median", "mean"):
            name = f"global-{agg}"
            for dmin in DMINS:
                run_one(
                    name, cols,
                    lambda ch, rh, cq, dmin=dmin, agg=agg:
                        global_estimate(ch, rh, cq, dmin=dmin, agg=agg),
                    dmin,
                )

    print("\n=== surfaces (lin / poly2 / ridge) ===")
    for dew, cols in (("TT", COND2), ("TTdew", COND3)):
        for kind in ("lin", "poly2", "ridge"):
            name = kind
            for dmin in DMINS:
                run_one(
                    name, cols,
                    lambda ch, rh, cq, dmin=dmin, kind=kind:
                        fitted_estimate(ch, rh, cq, dmin=dmin, kind=kind),
                    dmin,
                )

    print("\n=== forêt (dmin=0 seulement : surface, pas un lookup) ===")
    for dew, cols in (("TT", COND2), ("TTdew", COND3)):
        run_one("rf", cols, rf_estimate, 0.0)

    df_tab = pd.DataFrame(rows)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    df_tab.to_csv(TABLE, index=False)
    print(f"\ntableau → {TABLE}")

    # best among dmin=0 TT (no dew), excluding the sklearn trap
    at0 = df_tab[(df_tab.dmin == 0.0) & (df_tab.dew == "TT")]
    best0 = at0.sort_values("acc", ascending=False).iloc[0]
    print(f"meilleur @ dmin=0 TT : {best0.estimator}  acc={best0.acc:.3f}")

    at05 = df_tab[(df_tab.dmin == 0.5) & (df_tab.dew == "TT")]
    best05 = at05.sort_values("acc", ascending=False).iloc[0]
    print(f"meilleur @ dmin=0.5 TT : {best05.estimator}  acc={best05.acc:.3f}")

    knn5 = df_tab[(df_tab.estimator == "knn-k5-median-unif") & (df_tab.dew == "TT")]
    print("\nkNN k=5 médiane (T,T) — la courbe :")
    for _, r in knn5.sort_values("dmin").iterrows():
        print(f"  dmin={r.dmin:4g}  acc={r.acc:.3f}  F1={r.f1:.3f}")

    # dew effect at dmin=0 knn5
    knn5_dew = df_tab[(df_tab.estimator == "knn-k5-median-unif") & (df_tab.dew == "TTdew") & (df_tab.dmin == 0.0)].iloc[0]
    knn5_tt = knn5[knn5.dmin == 0.0].iloc[0]
    print(
        f"\nrosée @ knn5-median dmin=0 : acc {knn5_tt.acc:.3f} → {knn5_dew.acc:.3f}  "
        f"mae_h {knn5_tt.mae_healthy:.4f} → {knn5_dew.mae_healthy:.4f}"
    )

    # per-class for knn5 dmin0, knn5 dmin0.5, best@0.5
    def log_per_class(key, tag):
        r = stored[key]
        p, rec, f1, sup = precision_recall_fscore_support(
            r["y_true"], r["y_hat"], labels=LABELS, zero_division=0
        )
        print(f"\npar panne — {tag}")
        for lab, fi, s in zip(LABELS, f1, sup):
            print(f"  {lab:16s}  F1={fi:.3f}  n={int(s)}")
            log(
                experiment="X3", protocol="LOMO", reference=tag,
                features="residuals", model="gradient-boosting",
                label=lab, metric="f1", value=float(fi), n=int(s),
            )

    log_per_class(("knn-k5-median-unif", "TT", 0.0), "knn-k5-median-unif-TT-dmin0")
    log_per_class(("knn-k5-median-unif", "TT", 0.5), "knn-k5-median-unif-TT-dmin0.5")
    log_per_class((best05.estimator, "TT", 0.5), f"{best05.estimator}-TT-dmin0.5")

    # figure: dmin → accuracy
    fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=140)
    series = [
        ("knn-k5-median-unif", "TT", "kNN k=5 médiane — publié", BLUE, 2.4, "-"),
        ("knn-k1-median-unif", "TT", "kNN k=1 médiane", ORANGE, 1.8, "-"),
        ("knn-k5-mean-unif", "TT", "kNN k=5 moyenne", MUTED, 1.4, "--"),
        ("global-median", "TT", "médiane globale", AQUA, 1.6, "-"),
        ("knn-k5-median-unif", "TTdew", "kNN k=5 médiane + rosée", BLUE, 1.4, ":"),
    ]
    # add best-at-0.5 if not already in the list
    extra = (best05.estimator, "TT", f"meilleur @ 0,5 °C ({best05.estimator})", "#7a3e9d", 1.8, "-.")
    if extra[0] not in {s[0] for s in series}:
        series.append(extra)

    for est, dew, lab, color, lw, ls in series:
        sub = df_tab[(df_tab.estimator == est) & (df_tab.dew == dew)].sort_values("dmin")
        if sub.empty:
            continue
        ax.plot(sub.dmin, sub.acc, ls, color=color, lw=lw, marker="o", ms=5, label=lab)

    ax.axhline(0.251, color=GRID, lw=1, ls=":")
    ax.text(2.02, 0.251, "majorité", va="bottom", ha="right", color=MUTED, fontsize=8)
    ax.set_xlabel("dmin (°C) — voisins plus proches exclus")
    ax.set_ylabel("accuracy LOMO (moyenne des deux plis)")
    ax.set_title("La référence saine n'est utile que si elle est proche")
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    ax.set_xlim(-0.05, 2.15)
    ax.set_ylim(0.22, 0.75)
    fig.tight_layout()
    fig.savefig(FIG, bbox_inches="tight", dpi=140)
    print(f"\nfigure → {FIG}")
    print(f"durée {time.time() - t0:.0f}s")
    return df_tab, stored, ctrl, trap, best0, best05


if __name__ == "__main__":
    main()
