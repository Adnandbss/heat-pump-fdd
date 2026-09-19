"""Feature contract and simulator mapping."""

from dataclasses import replace

from src.fdd.features import FEATURE_COLUMNS, cycle_to_features, healthy_cycle
from src.physics.simulator import HeatPumpSimulator
from src.studies.synthetic.generator import FaultDataGenerator, FaultType


def test_feature_count():
    assert len(FEATURE_COLUMNS) == 23
    assert "pressure_ratio" not in FEATURE_COLUMNS
    assert "compression_ratio" in FEATURE_COLUMNS


def test_features_module_has_no_study_taxonomy():
    import src.fdd.features as features

    assert not hasattr(features, "SCENARIOS")
    assert not hasattr(features, "FAULT_PARAM_MAP")


def test_cycle_to_features_keys():
    sim = HeatPumpSimulator()
    result = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    row = cycle_to_features(result, 7, 40, 0.7)
    assert set(row) == set(FEATURE_COLUMNS)


def test_generator_sample():
    gen = FaultDataGenerator(random_seed=0)
    sample = gen.generate_single_sample(7, 40, 0.7, FaultType.NORMAL, 0.0)
    for col in FEATURE_COLUMNS:
        assert col in sample
    assert sample["fault_type"] == "Normal"


def test_default_baseline_is_a_simulated_healthy_cycle():
    sim = HeatPumpSimulator()
    result = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    implicit = cycle_to_features(result, 7, 40, 0.7, simulator=sim)
    explicit = cycle_to_features(
        result, 7, 40, 0.7, baseline=healthy_cycle(7, 40, 0.7, sim), simulator=sim
    )
    for key in ("d_COP", "d_W_comp", "d_T_discharge", "d_superheat", "d_subcooling"):
        assert abs(implicit[key] - explicit[key]) < 1e-9


def test_injected_baseline_changes_only_residuals():
    sim = HeatPumpSimulator()
    faulted = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, condenser_fouling=0.40)
    simulated = cycle_to_features(faulted, 7, 40, 0.7, simulator=sim)
    other = replace(healthy_cycle(7, 40, 0.7, sim), COP=faulted.COP - 1.0)
    measured = cycle_to_features(faulted, 7, 40, 0.7, baseline=other, simulator=sim)
    assert measured["COP"] == simulated["COP"]
    assert measured["d_COP"] == 1.0
    assert measured["d_COP"] != simulated["d_COP"]


def test_fouling_and_fan_signatures_differ():
    sim = HeatPumpSimulator()
    base = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    fouling = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, condenser_fouling=0.40)
    fan = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, fan_cond_ratio=0.55)
    # NIST: condenser blockage backs liquid up → subcooling rises.
    assert fouling.subcooling > base.subcooling
    # Condenser fan still distinguishable: smaller subcooling shift, higher discharge.
    assert abs(fouling.subcooling - base.subcooling) > abs(fan.subcooling - base.subcooling)
    assert fan.T_discharge > fouling.T_discharge
