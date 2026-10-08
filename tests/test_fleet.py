"""Fleet triage: the evidence gate decides what earns a dispatch."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import fleet_policy as policy
from api.routers.fleet import SimulatedUnit, triage
from src.studies.synthetic.paths import CLASSIFIER_PATH
from tools.results import RESULTS_PATH

needs_model = pytest.mark.skipif(
    not CLASSIFIER_PATH.exists(), reason="Train the model with main_analysis.py first"
)


def _results() -> pd.DataFrame:
    return pd.read_csv(RESULTS_PATH)


def _unit(diagnosis: str, confidence: float, unit_id: str = "HP-001") -> SimulatedUnit:
    return SimulatedUnit(
        unit_id=unit_id,
        T_source=7.0,
        T_sink=40.0,
        speed_ratio=0.7,
        injected=diagnosis,
        severity=0.3,
        diagnosis=diagnosis,
        confidence=confidence,
    )


def test_evidence_status_reads_results_csv():
    table = policy.evidence_by_class(_results())
    assert policy.evidence_for("Refrigerant_Undercharge", table).status == policy.TRANSFERS
    assert policy.evidence_for("Refrigerant_Overcharge", table).status == policy.TRANSFERS
    assert policy.evidence_for("Condenser_Fouling", table).status == policy.DOES_NOT_TRANSFER
    assert policy.evidence_for("Evaporator_Fan_Fault", table).status == policy.DOES_NOT_TRANSFER
    assert policy.evidence_for("Evaporator_Fouling", table).status == policy.UNTESTED


def test_a_better_logged_f1_flips_condenser_fouling_to_transfers():
    results = _results()
    row = (
        (results["experiment"] == policy.EVIDENCE_EXPERIMENT)
        & (results["protocol"] == policy.EVIDENCE_PROTOCOL)
        & (results["metric"] == "f1")
        & (results["label"] == "Condenser_Fouling")
    )
    assert row.sum() == 1
    results.loc[row, "value"] = policy.EVIDENCE_F1_MIN + 0.1

    response = triage([_unit("Condenser_Fouling", 0.95)], results, validated_only=True, seed=0)

    assert response.units[0].evidence.status == policy.TRANSFERS
    assert response.units[0].action == policy.DISPATCH


@pytest.mark.parametrize("label", ["Condenser_Fouling", "Evaporator_Fan_Fault", "Evaporator_Fouling"])
def test_gate_never_dispatches_a_class_without_measured_evidence(label):
    gated = triage([_unit(label, 0.99)], _results(), validated_only=True, seed=0)
    assert gated.units[0].action == policy.ENGINEERING_REVIEW
    assert gated.summary.held_back == 1

    ungated = triage([_unit(label, 0.99)], _results(), validated_only=False, seed=0)
    assert ungated.units[0].action == policy.DISPATCH
    assert ungated.summary.held_back == 0


def test_validated_fault_with_confidence_is_dispatched_with_an_instruction():
    response = triage([_unit("Refrigerant_Undercharge", 0.9)], _results(), validated_only=True, seed=0)
    unit = response.units[0]
    assert unit.action == policy.DISPATCH
    assert unit.instruction == policy.DISPATCH_INSTRUCTIONS["Refrigerant_Undercharge"]


@pytest.mark.parametrize("label", ["Refrigerant_Undercharge", "Normal"])
def test_low_confidence_is_monitored_not_dispatched_nor_cleared(label):
    response = triage(
        [_unit(label, policy.CONFIDENCE_MIN - 0.1)], _results(), validated_only=True, seed=0
    )
    assert response.units[0].action == policy.MONITOR


def test_confident_healthy_unit_needs_no_action():
    response = triage([_unit("Normal", 0.95)], _results(), validated_only=True, seed=0)
    assert response.units[0].action == policy.NO_ACTION


def test_missing_results_log_dispatches_nothing():
    units = [_unit("Refrigerant_Undercharge", 0.95), _unit("Refrigerant_Overcharge", 0.95, "HP-002")]
    response = triage(units, pd.DataFrame(), validated_only=True, seed=0)
    assert {u.evidence.status for u in response.units} == {policy.UNTESTED}
    assert response.summary.dispatch == 0


def test_summary_counts_match_rows_and_order_follows_priority():
    units = [
        _unit("Normal", 0.95, "HP-001"),
        _unit("Condenser_Fouling", 0.9, "HP-002"),
        _unit("Refrigerant_Undercharge", 0.9, "HP-003"),
        _unit("Refrigerant_Overcharge", 0.5, "HP-004"),
    ]
    response = triage(units, _results(), validated_only=True, seed=0)
    summary = response.summary
    assert summary.units == len(response.units) == 4
    assert summary.dispatch + summary.engineering_review + summary.monitor + summary.no_action == 4
    assert [u.action for u in response.units] == [
        policy.DISPATCH,
        policy.ENGINEERING_REVIEW,
        policy.MONITOR,
        policy.NO_ACTION,
    ]


@needs_model
def test_simulate_returns_the_same_service_decision_as_the_queue():
    from api.app import app

    client = TestClient(app)
    response = client.post(
        "/simulate",
        json={"T_source": 7, "T_sink": 40, "speed_ratio": 0.7, "fault_type": "Condenser_Fouling"},
    )
    assert response.status_code == 200
    decision = response.json()["service_decision"]
    assert decision["action"] == "engineering_review"
    assert decision["evidence_status"] == "does_not_transfer"


@needs_model
def test_fleet_is_deterministic_for_a_seed():
    from api.routers.fleet import build_fleet
    from src.fdd.inference import FDDEngine
    from src.studies.synthetic.scenarios import SyntheticScenarios

    engine = FDDEngine()
    first = build_fleet(SyntheticScenarios(engine), size=8, seed=3)
    second = build_fleet(SyntheticScenarios(engine), size=8, seed=3)
    assert first == second
    assert len(first) == 8


@needs_model
def test_fleet_route_gates_dispatch_and_reports_what_it_held_back():
    from api.app import app
    from api.main import create_app
    from api.settings import Settings

    gated = TestClient(app).get("/api/fleet", params={"size": 24, "seed": 7})
    assert gated.status_code == 200
    body = gated.json()
    assert body["policy"]["validated_only"] is True
    assert body["summary"]["units"] == len(body["units"]) == 24
    for unit in body["units"]:
        if unit["action"] == "dispatch":
            assert unit["evidence"]["status"] == "transfers"
    assert [u["priority"] for u in body["units"]] == sorted(u["priority"] for u in body["units"])

    with TestClient(create_app(Settings(fleet_validated_only=False))) as client:
        ungated = client.get("/api/fleet", params={"size": 24, "seed": 7}).json()
    assert ungated["summary"]["held_back"] == 0
    assert ungated["summary"]["dispatch"] == body["summary"]["dispatch"] + body["summary"]["held_back"]
