"""Synthetic study: inject a fault, then diagnose through FDDEngine."""

from pathlib import Path

import pytest

from src.features import FEATURE_COLUMNS
from src.studies.synthetic.scenarios import FAULT_PARAM_MAP, SyntheticScenarios

MODEL_PATH = Path("models/fdd_classifier.joblib")
needs_model = pytest.mark.skipif(
    not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first"
)


def test_fault_param_map_covers_the_six_demo_classes():
    assert FAULT_PARAM_MAP["Normal"] == {}
    assert set(FAULT_PARAM_MAP) == {
        "Normal",
        "Condenser_Fouling",
        "Evaporator_Fouling",
        "Refrigerant_Undercharge",
        "Condenser_Fan_Fault",
        "Evaporator_Fan_Fault",
    }
    assert FAULT_PARAM_MAP["Condenser_Fouling"] == {"condenser_fouling": 0.40}
    assert FAULT_PARAM_MAP["Condenser_Fan_Fault"] == {"fan_cond_ratio": 0.55}
    assert FAULT_PARAM_MAP["Refrigerant_Undercharge"] == {"refrigerant_charge": 0.80}


def test_package_reexports_scenarios():
    from src.studies.synthetic import FAULT_PARAM_MAP as exported_map
    from src.studies.synthetic import SyntheticScenarios as Exported

    assert exported_map is FAULT_PARAM_MAP
    assert Exported is SyntheticScenarios


@needs_model
def test_simulate_cycle_payload_shape():
    from src.inference import FDDEngine

    engine = FDDEngine()
    payload = SyntheticScenarios(engine).simulate_cycle(fault_type="Normal")
    assert set(payload) == {"conditions", "cycle", "features", "diagnosis"}
    assert payload["conditions"]["injected_fault"] == "Normal"
    assert set(payload["features"]) == set(FEATURE_COLUMNS)
    assert payload["cycle"]["P_cond"] > payload["cycle"]["P_evap"]
    assert payload["cycle"]["COP"] > 1.5
    assert payload["diagnosis"]["label"] in engine.class_names


@needs_model
def test_unknown_fault_name_falls_back_to_healthy_params():
    from src.inference import FDDEngine

    payload = SyntheticScenarios(FDDEngine()).simulate_cycle(fault_type="Not_A_Fault")
    assert payload["conditions"]["injected_fault"] == "Not_A_Fault"
    assert payload["cycle"]["COP"] > 1.5


@needs_model
def test_severity_overrides_default_map():
    from src.inference import FDDEngine

    scenarios = SyntheticScenarios(FDDEngine())
    mild = scenarios.simulate_cycle(fault_type="Condenser_Fouling", severity=0.10)
    harsh = scenarios.simulate_cycle(fault_type="Condenser_Fouling", severity=0.40)
    assert mild["cycle"]["COP"] >= harsh["cycle"]["COP"]


@needs_model
def test_fault_overrides_win_over_the_map():
    from src.inference import FDDEngine

    scenarios = SyntheticScenarios(FDDEngine())
    zero = scenarios.simulate_cycle(
        fault_type="Condenser_Fouling", condenser_fouling=0.0
    )
    mapped = scenarios.simulate_cycle(fault_type="Condenser_Fouling")
    assert zero["cycle"]["COP"] > mapped["cycle"]["COP"]


@needs_model
def test_live_trace_stays_normal_before_inject():
    from src.inference import FDDEngine

    trace = SyntheticScenarios(FDDEngine()).live_trace(
        fault_type="Condenser_Fouling",
        inject_at=4,
        n_points=8,
        severity_final=0.40,
    )
    assert len(trace) == 8
    assert list(trace["injected_fault"].iloc[:4]) == ["Normal"] * 4
    assert (trace["severity"].iloc[:4] == 0.0).all()
    assert (trace["injected_fault"].iloc[4:] == "Condenser_Fouling").all()
    assert trace["severity"].iloc[-1] > 0.0
    assert {"t", "P_cond", "COP", "predicted", "confidence"} <= set(trace.columns)


@needs_model
def test_live_trace_normal_never_injects():
    from src.inference import FDDEngine

    trace = SyntheticScenarios(FDDEngine()).live_trace(
        fault_type="Normal", inject_at=2, n_points=5
    )
    assert (trace["injected_fault"] == "Normal").all()
    assert (trace["severity"] == 0.0).all()
