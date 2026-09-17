"""Thermodynamic sanity checks."""

from src.physics.simulator import HAS_COOLPROP, HeatPumpSimulator, RefrigerantProperties


def test_r410a_saturation_pressure_at_0c():
    p = RefrigerantProperties.saturation_pressure(0.0)
    assert 7.5 < p < 8.5
    if HAS_COOLPROP:
        assert abs(p - 8.0) < 0.1


def test_nominal_cycle_cop():
    result = HeatPumpSimulator().simulate_cycle(T_source=7.0, T_sink=40.0, speed_ratio=0.7)
    assert result.COP > 1.5
    assert result.P_cond > result.P_evap
    assert result.T_discharge > result.T_suction


def test_discharge_temperature_stays_within_envelope():
    """T_discharge_max is a hard cap on the training domain, not a log string."""
    import numpy as np

    sim = HeatPumpSimulator()
    for T_source in np.linspace(-10.0, 20.0, 7):
        for T_sink in np.linspace(30.0, 55.0, 6):
            for speed_ratio in np.linspace(0.3, 1.0, 5):
                result = sim.simulate_cycle(
                    T_source=float(T_source),
                    T_sink=float(T_sink),
                    speed_ratio=float(speed_ratio),
                )
                assert result.T_discharge <= sim.T_discharge_max + 1e-6
    named = sim.simulate_cycle(T_source=-10.0, T_sink=55.0, speed_ratio=1.0)
    assert named.T_discharge <= 130.0
