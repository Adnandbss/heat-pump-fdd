"""Thermodynamic lab routes. All stay synchronous `def`."""

from __future__ import annotations

from typing import List, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from api.deps import get_dataset, get_saturation_curve
from api.schemas.dashboard import (
    AshraeResponse,
    AshraeRow,
    CopCurvePoint,
    CopMeasuredPoint,
    CopResponse,
    Envelope,
    EnvelopeZone,
    PhCompareResponse,
    PhCyclePoint,
    PhOverlay,
    PhResponse,
    SweepPoint,
    SweepResponse,
)
from src.physics.thermo_lab import (
    ashrae_table,
    condenser_sweep,
    cycle_state,
    evaporator_sweep,
    sweep_deltas,
)
from src.physics.thermodynamic_viz import HAS_COOLPROP

router = APIRouter(tags=["thermo"])


def _ph_overlay(
    t_evap: float,
    t_cond: float,
    superheat: float,
    subcooling: float,
    eta_is: float = 0.75,
) -> PhOverlay:
    state = cycle_state(t_evap, t_cond, superheat, subcooling, eta_is)
    return PhOverlay(
        T_evap=state["T_evap"],
        T_cond=state["T_cond"],
        P_evap=state["P_evap"],
        P_cond=state["P_cond"],
        COP=state["COP"],
        cycle=[
            PhCyclePoint(name="1 suction", h=state["h1"], P=state["P_evap"]),
            PhCyclePoint(name="2 discharge", h=state["h2"], P=state["P_cond"]),
            PhCyclePoint(name="3 liquid", h=state["h3"], P=state["P_cond"]),
            PhCyclePoint(name="4 two-phase", h=state["h4"], P=state["P_evap"]),
            PhCyclePoint(name="1 suction", h=state["h1"], P=state["P_evap"]),
        ],
    )


@router.get(
    "/api/thermo/ph",
    response_model=PhResponse,
    summary="P-h diagram for one operating point",
    operation_id="getPhDiagram",
)
def api_thermo_ph(
    T_evap: float = Query(5.0),
    T_cond: float = Query(45.0),
    superheat: float = Query(6.0, ge=0.0, le=20.0),
    subcooling: float = Query(5.0, ge=0.0, le=20.0),
    eta_is: float = Query(0.75, ge=0.4, le=1.0),
    saturation=Depends(get_saturation_curve),
) -> PhResponse:
    overlay = _ph_overlay(T_evap, T_cond, superheat, subcooling, eta_is)
    return PhResponse(
        coolprop=HAS_COOLPROP,
        P_evap=overlay.P_evap,
        P_cond=overlay.P_cond,
        COP=overlay.COP,
        saturation=list(saturation),
        cycle=overlay.cycle,
        envelope=Envelope(
            normal=EnvelopeZone(T_evap=[-20, 20], T_cond=[25, 65]),
            extended=EnvelopeZone(T_evap=[-30, 25], T_cond=[20, 70]),
        ),
    )


@router.get(
    "/api/thermo/ph/compare",
    response_model=PhCompareResponse,
    summary="Nominal P-h overlay against condenser and evaporator load",
    operation_id="getPhCompare",
)
def api_thermo_ph_compare(
    T_evap: float = Query(0.0, ge=-10.0, le=10.0),
    T_cond: float = Query(45.0, ge=35.0, le=55.0),
    superheat: float = Query(8.0, ge=2.0, le=15.0),
    subcooling: float = Query(5.0, ge=2.0, le=12.0),
    load_factor: float = Query(50.0, ge=30.0, le=100.0),
    t_source: float = Query(-10.0, ge=-15.0, le=15.0),
    scenario: Literal["nominal", "condenser", "evaporator", "all"] = Query("all"),
    saturation=Depends(get_saturation_curve),
) -> PhCompareResponse:
    nominal = _ph_overlay(T_evap, T_cond, superheat, subcooling)
    condenser = None
    evaporator = None
    if scenario in ("condenser", "all"):
        t_cond_load = T_cond + (100.0 - load_factor) / 100.0 * 15.0
        condenser = _ph_overlay(T_evap, t_cond_load, superheat, subcooling)
    if scenario in ("evaporator", "all"):
        evaporator = _ph_overlay(t_source - 5.0, T_cond, superheat, subcooling)
    return PhCompareResponse(
        coolprop=HAS_COOLPROP,
        scenario=scenario,
        saturation=list(saturation),
        nominal=nominal,
        condenser=condenser,
        evaporator=evaporator,
    )


@router.get(
    "/api/thermo/cop",
    response_model=CopResponse,
    summary="Heating Carnot envelope and measured Normal COP vs ambient",
    operation_id="getCopCurve",
)
def api_thermo_cop(
    T_sink: float = Query(40.0, ge=25.0, le=60.0),
    df: pd.DataFrame = Depends(get_dataset),
) -> CopResponse:
    t_max = T_sink - 10.0
    T_amb = np.linspace(-10.0, t_max, 40)
    t_sink_k = T_sink + 273.15
    carnot = t_sink_k / np.maximum(t_sink_k - (T_amb + 273.15), 1.0)
    half = float((T_amb[1] - T_amb[0]) / 2.0) if len(T_amb) > 1 else 1.0

    normal = pd.DataFrame()
    if {"T_ambient", "COP", "fault_type"}.issubset(df.columns):
        normal = df.loc[
            (df["fault_type"] == "Normal") & df["T_ambient"].notna() & df["COP"].notna(),
            ["T_ambient", "COP"],
        ]

    curves: List[CopCurvePoint] = []
    for t, c in zip(T_amb, carnot):
        band = normal.loc[
            (normal["T_ambient"] >= t - half) & (normal["T_ambient"] < t + half)
        ] if not normal.empty else normal
        n = int(len(band))
        estimated = float(band["COP"].mean()) if n else None
        curves.append(
            CopCurvePoint(
                T_amb=float(t),
                carnot=float(c),
                estimated=estimated,
                n=n if n else None,
            )
        )

    measured: List[CopMeasuredPoint] = []
    if not normal.empty:
        sample = normal.sample(n=min(400, len(normal)), random_state=0)
        measured = [
            CopMeasuredPoint(T_amb=float(row["T_ambient"]), COP=float(row["COP"]))
            for row in sample.to_dict(orient="records")
        ]
    return CopResponse(curves=curves, measured=measured)


@router.get(
    "/api/thermo/sweep/condenser",
    response_model=SweepResponse,
    summary="Condenser-load sweep of COP and compressor power",
    operation_id="getCondenserSweep",
)
def api_sweep_condenser(
    T_evap: float = Query(0.0, ge=-10.0, le=10.0),
    load_min: float = Query(30.0, ge=20.0, le=90.0),
    load_max: float = Query(100.0, ge=40.0, le=100.0),
) -> SweepResponse:
    lo, hi = min(load_min, load_max), max(load_min, load_max)
    points = condenser_sweep(t_evap=T_evap, load_min=lo, load_max=hi)
    return SweepResponse(
        kind="condenser",
        coolprop=HAS_COOLPROP,
        points=[SweepPoint.model_validate(row) for row in points],
        deltas=sweep_deltas(points, ["COP", "W_comp", "tau", "T_dis"]),
        headline="Main impact: compressor power up",
    )


@router.get(
    "/api/thermo/sweep/evaporator",
    response_model=SweepResponse,
    summary="Source-temperature sweep of heating capacity",
    operation_id="getEvaporatorSweep",
)
def api_sweep_evaporator(
    T_cond: float = Query(45.0, ge=35.0, le=55.0),
    source_min: float = Query(-15.0, ge=-20.0, le=5.0),
    source_max: float = Query(7.0, ge=-5.0, le=15.0),
) -> SweepResponse:
    lo, hi = min(source_min, source_max), max(source_min, source_max)
    points = evaporator_sweep(t_cond=T_cond, source_min=lo, source_max=hi)
    return SweepResponse(
        kind="evaporator",
        coolprop=HAS_COOLPROP,
        points=[SweepPoint.model_validate(row) for row in points],
        deltas=sweep_deltas(points, ["COP", "P_evap", "tau", "Q_evap"]),
        headline="Main impact: heating capacity down",
    )


@router.get(
    "/api/thermo/ashrae",
    response_model=AshraeResponse,
    summary="R410A saturation pressure vs the ASHRAE table",
    operation_id="getAshraeTable",
)
def api_thermo_ashrae() -> AshraeResponse:
    return AshraeResponse(
        coolprop=HAS_COOLPROP,
        rows=[AshraeRow.model_validate(row) for row in ashrae_table()],
    )
