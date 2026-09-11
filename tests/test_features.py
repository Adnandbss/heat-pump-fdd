"""Feature contract and simulator mapping."""

from src.features import FEATURE_COLUMNS, cycle_to_features
from src.data_generator import FaultDataGenerator, FaultType
from src.simulator import HeatPumpSimulator


def test_feature_count():
    assert len(FEATURE_COLUMNS) == 24


def test_features_module_has_no_study_taxonomy():
    import src.features as features

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


def test_fouling_and_fan_signatures_differ():
    sim = HeatPumpSimulator()
    base = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    fouling = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, condenser_fouling=0.40)
    fan = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, fan_cond_ratio=0.55)
    assert (base.subcooling - fouling.subcooling) > (base.subcooling - fan.subcooling)
    assert fan.T_discharge > fouling.T_discharge
