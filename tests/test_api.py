"""Inference and API contract tests."""

import pytest
from fastapi.testclient import TestClient

from src.studies.synthetic.paths import CLASSIFIER_PATH

MODEL_PATH = CLASSIFIER_PATH


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_normal_point_is_diagnosed():
    from src.fdd.inference import FDDEngine
    from src.studies.synthetic.scenarios import SyntheticScenarios

    engine = FDDEngine()
    payload = SyntheticScenarios(engine).simulate_cycle(
        T_source=7, T_sink=40, speed_ratio=0.7, fault_type="Normal"
    )
    assert payload["diagnosis"]["label"] in engine.class_names
    assert 0.0 <= payload["diagnosis"]["confidence"] <= 1.0
    assert len(payload["features"]) == 24


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_condenser_fouling_is_not_confused_with_fan():
    from src.fdd.inference import FDDEngine
    from src.studies.synthetic.scenarios import SyntheticScenarios

    engine = FDDEngine()
    scenarios = SyntheticScenarios(engine)
    payload = scenarios.simulate_cycle(
        T_source=7, T_sink=40, speed_ratio=0.7, fault_type="Condenser_Fouling"
    )
    assert payload["diagnosis"]["label"] == "Condenser_Fouling"

    leak = scenarios.simulate_cycle(
        T_source=7, T_sink=40, speed_ratio=0.7, fault_type="Refrigerant_Undercharge"
    )
    assert leak["diagnosis"]["label"] == "Refrigerant_Undercharge"


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_api_health_and_simulate():
    from api.app import app

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.post(
        "/simulate",
        json={"T_source": 7, "T_sink": 40, "speed_ratio": 0.7, "fault_type": "Normal"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "diagnosis" in body
    assert "cycle" in body


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_api_live_trace_injects_fouling():
    from api.app import app

    client = TestClient(app)
    response = client.post(
        "/live",
        json={
            "fault_type": "Condenser_Fouling",
            "inject_at": 8,
            "n_points": 20,
        },
    )
    assert response.status_code == 200
    trace = response.json()["trace"]
    assert len(trace) == 20
    assert trace[-1]["predicted"] == "Condenser_Fouling"


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_service_falls_back_when_api_is_down():
    from src.service import FDDService

    service = FDDService(api_url="http://127.0.0.1:9")
    payload, mode = service.simulate_cycle(fault_type="Normal")
    assert mode == "local"
    assert payload["diagnosis"]["label"] == "Normal"


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_dashboard_facade_and_cors():
    from api.app import app

    client = TestClient(app)
    headers = {"Origin": "http://localhost:5173"}

    stats = client.get("/api/stats", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert "COP" in body and "label" in body and "P_cond" in body
    assert stats.headers.get("access-control-allow-origin") == "http://localhost:5173"

    overview = client.get("/api/overview")
    assert overview.status_code == 200
    classes = overview.json()["classes"]
    assert len(classes) >= 6
    assert all("name" in row and "value" in row for row in classes)

    activity = client.get("/api/activity", params={"n_points": 12, "inject_at": 6})
    assert activity.status_code == 200
    trace = activity.json()["trace"]
    assert len(trace) == 12
    assert {"t", "P_cond", "COP", "predicted"} <= set(trace[-1])

    challenges = client.get("/api/challenges")
    assert challenges.status_code == 200
    items = challenges.json()["challenges"]
    assert len(items) >= 5
    assert {row["status"] for row in items} <= {"On Going", "Complete"}


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_ml_dashboard_payloads():
    from api.app import app

    client = TestClient(app)

    catalog = client.get("/api/catalog")
    assert catalog.status_code == 200
    titles = [row["fault_type"] for row in catalog.json()["scenarios"]]
    assert len(titles) == 7
    assert "Refrigerant_Overcharge" in titles
    assert "Compressor_Valve_Leak" not in titles
    assert "superheat" in catalog.json()["features"]

    models = client.get("/api/models")
    assert models.status_code == 200
    body = models.json()
    assert body["comparison"]
    assert "F1 Score" in body["comparison"][0]
    assert len(body["confusion"]["labels"]) >= 6
    assert body["importance"]

    dataset = client.get("/api/dataset")
    assert dataset.status_code == 200
    assert dataset.json()["n_samples"] > 100

    dist = client.get("/api/explore/distribution", params={"feature": "COP"})
    assert dist.status_code == 200
    assert len(dist.json()["boxes"]) >= 6

    scatter = client.get("/api/explore/scatter", params={"x": "COP", "y": "P_cond", "limit": 120})
    assert scatter.status_code == 200
    assert len(scatter.json()["points"]) >= 60

    advanced = client.get("/api/advanced")
    assert advanced.status_code == 200
    assert len(advanced.json()["labels"]) >= 6

    ph = client.get("/api/thermo/ph", params={"T_evap": 5, "T_cond": 45})
    assert ph.status_code == 200
    assert len(ph.json()["cycle"]) == 5
    assert ph.json()["COP"] > 0

    cop = client.get("/api/thermo/cop")
    assert cop.status_code == 200
    assert cop.json()["curves"]

    condenser = client.get("/api/thermo/sweep/condenser", params={"T_evap": 0, "load_min": 40, "load_max": 100})
    assert condenser.status_code == 200
    assert len(condenser.json()["points"]) == 20
    assert condenser.json()["points"][0]["COP"] > 0

    evap = client.get("/api/thermo/sweep/evaporator", params={"T_cond": 45})
    assert evap.status_code == 200
    assert evap.json()["headline"]

    ashrae = client.get("/api/thermo/ashrae")
    assert ashrae.status_code == 200
    assert len(ashrae.json()["rows"]) >= 8

    ambient = client.get("/api/advanced/ambient")
    assert ambient.status_code == 200
    assert len(ambient.json()["y_labels"]) == 5
    assert ambient.json()["matrix"]

    compare = client.get(
        "/api/thermo/ph/compare",
        params={"scenario": "all", "load_factor": 50, "t_source": -10, "T_evap": 0, "T_cond": 45},
    )
    assert compare.status_code == 200
    body = compare.json()
    assert body["condenser"]["P_cond"] > body["nominal"]["P_cond"]
    assert body["evaporator"]["P_evap"] < body["nominal"]["P_evap"]
    assert len(body["saturation"]) > 10
    assert len(body["nominal"]["cycle"]) == 5


def test_pydantic_contracts_reject_unknown_fault():
    from api.app import app

    client = TestClient(app)
    response = client.post(
        "/simulate",
        json={"T_source": 7, "T_sink": 40, "speed_ratio": 0.7, "fault_type": "Not_A_Fault"},
    )
    assert response.status_code == 422


def test_feature_vector_and_diagnosis_schemas():
    from api.schemas import Diagnosis, FeatureVector, SimulateResponse
    from src.fdd.inference import FDDEngine
    from src.studies.synthetic.scenarios import SyntheticScenarios

    if not MODEL_PATH.exists():
        pytest.skip("Train the model with main_analysis.py first")

    payload = SyntheticScenarios(FDDEngine()).simulate_cycle(fault_type="Normal")
    parsed = SimulateResponse.model_validate(payload)
    assert parsed.diagnosis.label == "Normal"
    assert FeatureVector.model_validate(payload["features"]).COP > 0
    Diagnosis.model_validate(payload["diagnosis"])
