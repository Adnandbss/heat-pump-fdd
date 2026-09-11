"""CoolProp lab helpers: load sweeps, ASHRAE check, ambient heatmap."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.thermodynamic_viz import HAS_COOLPROP, R410A

FLUID = "R410A"
ETA_IS = 0.75

ASHRAE_PSAT = {
    -20: 4.00,
    -10: 5.72,
    0: 8.00,
    10: 10.88,
    20: 14.17,
    30: 18.72,
    40: 24.20,
    50: 30.40,
}


def _props():
    from CoolProp.CoolProp import PropsSI

    return PropsSI


def cycle_state(
    t_evap: float,
    t_cond: float,
    superheat: float = 8.0,
    subcooling: float = 5.0,
    eta_is: float = ETA_IS,
) -> Dict[str, float]:
    """One vapour-compression point (CoolProp when available)."""
    t_evap = float(np.clip(t_evap, -25.0, 20.0))
    t_cond = float(np.clip(t_cond, 20.0, 70.0))
    eta_is = float(np.clip(eta_is, 0.4, 1.0))
    if HAS_COOLPROP:
        try:
            PropsSI = _props()
            t_evap_k = t_evap + 273.15
            t_cond_k = t_cond + 273.15
            p_evap = PropsSI("P", "T", t_evap_k, "Q", 1, FLUID) / 1e5
            p_cond = PropsSI("P", "T", t_cond_k, "Q", 1, FLUID) / 1e5
            t1 = t_evap_k + superheat
            h1 = PropsSI("H", "T", t1, "P", p_evap * 1e5, FLUID)
            s1 = PropsSI("S", "T", t1, "P", p_evap * 1e5, FLUID)
            h2s = PropsSI("H", "S", s1, "P", p_cond * 1e5, FLUID)
            h2 = h1 + (h2s - h1) / eta_is
            t3 = t_cond_k - subcooling
            h3 = PropsSI("H", "T", t3, "P", p_cond * 1e5, FLUID)
            h4 = h3
            w_comp = (h2 - h1) / 1000.0
            q_cond = (h2 - h3) / 1000.0
            q_evap = (h1 - h4) / 1000.0
            cop = q_cond / w_comp if w_comp > 0 else 3.0
            t_dis = PropsSI("T", "H", h2, "P", p_cond * 1e5, FLUID) - 273.15
            return {
                "T_evap": t_evap,
                "T_cond": t_cond,
                "P_evap": float(p_evap),
                "P_cond": float(p_cond),
                "tau": float(p_cond / p_evap) if p_evap else 0.0,
                "COP": float(cop),
                "W_comp": float(w_comp),
                "Q_cond": float(q_cond),
                "Q_evap": float(q_evap),
                "T_dis": float(t_dis),
                "h1": float(h1 / 1000.0),
                "h2": float(h2 / 1000.0),
                "h3": float(h3 / 1000.0),
                "h4": float(h4 / 1000.0),
            }
        except Exception:
            pass
    p_evap = float(R410A.P_sat(t_evap))
    p_cond = float(R410A.P_sat(t_cond))
    tau = p_cond / p_evap if p_evap else 0.0
    cop = max(1.2, 4.0 - 0.08 * (t_cond - t_evap - 40.0))
    w_comp = 2.0 + 0.04 * (t_cond - 45.0)
    q_evap = 200.0 + 4.0 * t_evap
    return {
        "T_evap": t_evap,
        "T_cond": t_cond,
        "P_evap": p_evap,
        "P_cond": p_cond,
        "tau": tau,
        "COP": cop,
        "W_comp": w_comp,
        "Q_cond": cop * w_comp,
        "Q_evap": q_evap,
        "T_dis": 70.0 + 0.8 * (t_cond - 45.0),
        "h1": 420.0,
        "h2": 455.0,
        "h3": 250.0,
        "h4": 250.0,
    }


def condenser_sweep(
    t_evap: float = 0.0,
    load_min: float = 30.0,
    load_max: float = 100.0,
    n: int = 20,
) -> List[Dict[str, float]]:
    loads = np.linspace(load_max, load_min, n)
    t_conds = 45.0 + (100.0 - loads) / 100.0 * 15.0
    rows = []
    for load, t_cond in zip(loads, t_conds):
        state = cycle_state(t_evap, float(t_cond))
        state["load"] = float(load)
        rows.append(state)
    return rows


def evaporator_sweep(
    t_cond: float = 45.0,
    source_min: float = -15.0,
    source_max: float = 7.0,
    n: int = 20,
) -> List[Dict[str, float]]:
    sources = np.linspace(source_max, source_min, n)
    rows = []
    for t_source in sources:
        t_evap = float(t_source) - 5.0
        state = cycle_state(t_evap, t_cond)
        state["t_source"] = float(t_source)
        rows.append(state)
    return rows


def ashrae_table() -> List[Dict[str, float]]:
    rows = []
    for t_c, ashrae in ASHRAE_PSAT.items():
        coolprop = float(R410A.P_sat(float(t_c)))
        error = abs(coolprop - ashrae) / ashrae * 100.0 if ashrae else 0.0
        rows.append(
            {
                "T": float(t_c),
                "ashrae": float(ashrae),
                "coolprop": round(coolprop, 2),
                "error_pct": round(error, 2),
            }
        )
    return rows


def ambient_heatmap(df: pd.DataFrame) -> Tuple[List[str], List[str], List[List[int]]]:
    bins = ["Very cold", "Cold", "Mild", "Warm", "Hot"]
    work = df.copy()
    work["T_ambient_bin"] = pd.cut(work["T_ambient"], bins=5, labels=bins)
    table = (
        work.dropna(subset=["T_ambient_bin"])
        .groupby(["T_ambient_bin", "fault_type"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(bins, fill_value=0)
    )
    x_labels = [str(col) for col in table.columns]
    matrix = table.astype(int).values.tolist()
    return x_labels, bins, matrix


def sweep_deltas(rows: List[Dict[str, float]], keys: List[str]) -> Dict[str, float]:
    first, last = rows[0], rows[-1]
    out = {}
    for key in keys:
        base = first.get(key) or 1e-9
        out[key] = (last[key] - first[key]) / base * 100.0
    return out
