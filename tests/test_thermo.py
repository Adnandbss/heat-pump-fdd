"""Thermodynamic sanity checks."""

from src.simulator import HAS_COOLPROP, HeatPumpSimulator, RefrigerantProperties


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
