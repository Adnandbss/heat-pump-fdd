"""Feature contract shared by the simulator, ML pipeline, API and dashboard."""

from typing import Dict, List, Optional

from .simulator import CycleResults, HeatPumpSimulator

FEATURE_COLUMNS: List[str] = [
    "T_ambient",
    "T_setpoint",
    "compressor_speed_ratio",
    "P_evap",
    "P_cond",
    "T_evap",
    "T_cond",
    "T_suction",
    "T_discharge",
    "superheat",
    "subcooling",
    "compression_ratio",
    "W_comp",
    "Q_cond",
    "COP",
    "delta_T_evap",
    "delta_T_cond",
    "pressure_ratio",
    "capacity_ratio",
    "d_T_discharge",
    "d_superheat",
    "d_subcooling",
    "d_COP",
    "d_W_comp",
]

DEFAULT_CAPACITY_NOM = 10000.0


def healthy_cycle(
    T_source: float,
    T_sink: float,
    speed_ratio: float,
    simulator: Optional[HeatPumpSimulator] = None,
) -> CycleResults:
    sim = simulator or HeatPumpSimulator()
    return sim.simulate_cycle(T_source=T_source, T_sink=T_sink, speed_ratio=speed_ratio)


def cycle_to_features(
    result: CycleResults,
    T_source: float,
    T_sink: float,
    speed_ratio: float,
    capacity_nom: float = DEFAULT_CAPACITY_NOM,
    baseline: Optional[CycleResults] = None,
    simulator: Optional[HeatPumpSimulator] = None,
) -> Dict[str, float]:
    """Map a simulated cycle to the model vector, including Li-Braun residuals."""
    if baseline is None:
        baseline = healthy_cycle(T_source, T_sink, speed_ratio, simulator)
    return {
        "T_ambient": float(T_source),
        "T_setpoint": float(T_sink),
        "compressor_speed_ratio": float(speed_ratio),
        "P_evap": float(result.P_evap),
        "P_cond": float(result.P_cond),
        "T_evap": float(result.T_evap),
        "T_cond": float(result.T_cond),
        "T_suction": float(result.T_suction),
        "T_discharge": float(result.T_discharge),
        "superheat": float(result.superheat),
        "subcooling": float(result.subcooling),
        "compression_ratio": float(result.compression_ratio),
        "W_comp": float(result.W_comp),
        "Q_cond": float(result.Q_cond),
        "COP": float(result.COP),
        "delta_T_evap": float(T_source - result.T_evap),
        "delta_T_cond": float(result.T_cond - T_sink),
        "pressure_ratio": float(result.P_cond / result.P_evap) if result.P_evap else 0.0,
        "capacity_ratio": float(result.Q_cond / capacity_nom) if capacity_nom else 0.0,
        "d_T_discharge": float(result.T_discharge - baseline.T_discharge),
        "d_superheat": float(result.superheat - baseline.superheat),
        "d_subcooling": float(result.subcooling - baseline.subcooling),
        "d_COP": float(result.COP - baseline.COP),
        "d_W_comp": float(result.W_comp - baseline.W_comp),
    }
