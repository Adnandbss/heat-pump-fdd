"""FDDEngine diagnoses a feature vector; it does not own the synthetic study."""

from pathlib import Path

import pytest

from src.fdd.features import FEATURE_COLUMNS, cycle_to_features
from src.physics.simulator import HeatPumpSimulator

MODEL_PATH = Path("models/fdd_classifier.joblib")
needs_model = pytest.mark.skipif(
    not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first"
)


@needs_model
def test_engine_has_no_synthetic_study_api():
    from src.fdd.inference import FDDEngine

    engine = FDDEngine()
    assert not hasattr(engine, "simulate_cycle")
    assert not hasattr(engine, "live_trace")
    assert not hasattr(engine, "simulator")
    assert not hasattr(engine, "generator")


@needs_model
def test_engine_does_not_export_fault_param_map():
    import src.fdd.inference as inference

    assert not hasattr(inference, "FAULT_PARAM_MAP")


@needs_model
def test_engine_predicts_from_a_feature_vector():
    from src.fdd.inference import FDDEngine

    engine = FDDEngine()
    sim = HeatPumpSimulator()
    result = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    features = cycle_to_features(result, 7, 40, 0.7, sim.capacity_nom, simulator=sim)

    diagnosis = engine.predict(features)
    assert diagnosis["label"] in engine.class_names
    assert 0.0 <= diagnosis["confidence"] <= 1.0
    assert set(diagnosis["probabilities"]) == set(engine.class_names)
    assert abs(sum(diagnosis["probabilities"].values()) - 1.0) < 1e-6


@needs_model
def test_engine_predicts_from_a_dataframe():
    from src.fdd.inference import FDDEngine
    import pandas as pd

    engine = FDDEngine()
    sim = HeatPumpSimulator()
    result = sim.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7)
    features = cycle_to_features(result, 7, 40, 0.7, sim.capacity_nom, simulator=sim)

    diagnosis = engine.predict(pd.DataFrame([features]))
    assert diagnosis["label"] in engine.class_names


@needs_model
def test_engine_rejects_missing_features():
    from src.fdd.inference import FDDEngine

    engine = FDDEngine()
    with pytest.raises(ValueError, match="Missing features"):
        engine.predict({"COP": 3.0})


@needs_model
def test_engine_feature_names_match_contract():
    from src.fdd.inference import FDDEngine

    engine = FDDEngine()
    assert list(engine.feature_names) == FEATURE_COLUMNS
    assert len(engine.class_names) >= 6
