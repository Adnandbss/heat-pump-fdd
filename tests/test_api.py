"""Inference and API contract tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

MODEL_PATH = Path("models/fdd_classifier.joblib")


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_normal_point_is_diagnosed():
    from src.inference import FDDEngine

    engine = FDDEngine()
    payload = engine.simulate_cycle(T_source=7, T_sink=40, speed_ratio=0.7, fault_type="Normal")
    assert payload["diagnosis"]["label"] in engine.class_names
    assert 0.0 <= payload["diagnosis"]["confidence"] <= 1.0
    assert len(payload["features"]) == 24


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Train the model with main_analysis.py first")
def test_condenser_fouling_is_not_confused_with_fan():
    from src.inference import FDDEngine

    engine = FDDEngine()
    payload = engine.simulate_cycle(
        T_source=7, T_sink=40, speed_ratio=0.7, fault_type="Condenser_Fouling"
    )
    assert payload["diagnosis"]["label"] == "Condenser_Fouling"

    leak = engine.simulate_cycle(
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
