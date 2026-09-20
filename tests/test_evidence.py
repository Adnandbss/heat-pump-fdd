"""Evidence routes serve logged numbers from a CSV, with no classifier."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings
from tools.results import COLUMNS

TOY_ROWS = [
    {
        "experiment": "X0",
        "protocol": "leaked-dCOP",
        "reference": "simulated",
        "features": "24-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.996",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0",
        "protocol": "holdout-test-6class",
        "reference": "simulated",
        "features": "24-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.9187",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0",
        "protocol": "holdout-test",
        "reference": "simulated",
        "features": "23-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.893",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0b",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.602",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0b",
        "protocol": "random-cv",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.937",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0b",
        "protocol": "random-cv",
        "reference": "target-machine",
        "features": "raw",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.954",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0b",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "raw",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.333",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X0b",
        "protocol": "majority-class",
        "reference": "none",
        "features": "",
        "model": "baseline",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.251",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X5",
        "protocol": "sim2real",
        "reference": "measured-knn5",
        "features": "residuals",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.454",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO",
        "reference": "training-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.318",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "Overcharge",
        "metric": "f1",
        "value": "0.674",
        "n": "4",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO",
        "reference": "training-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "Overcharge",
        "metric": "f1",
        "value": "0.786",
        "n": "4",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "LiquidLine",
        "metric": "f1",
        "value": "0.04",
        "n": "4",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO",
        "reference": "training-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "LiquidLine",
        "metric": "f1",
        "value": "0.007",
        "n": "4",
        "note": "toy",
    },
    {
        "experiment": "X5",
        "protocol": "holdout-test",
        "reference": "simulated",
        "features": "residuals",
        "model": "random-forest",
        "label": "Refrigerant_Overcharge",
        "metric": "f1",
        "value": "0.936",
        "n": "4",
        "note": "toy",
    },
    {
        "experiment": "X3",
        "protocol": "LOMO",
        "reference": "knn-k5-median-unif-TT-dmin0",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.602",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X3",
        "protocol": "LOMO",
        "reference": "knn-k5-median-unif-TT-dmin0.5",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.482",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X4",
        "protocol": "holdout-random-control",
        "reference": "simulated",
        "features": "24-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.919",
        "n": "10",
        "note": "95% Wilson [0.90, 0.93]",
    },
    {
        "experiment": "X4",
        "protocol": "holdout-binary-severity-train>=0.20",
        "reference": "simulated",
        "features": "24-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.887",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X4",
        "protocol": "holdout-severity-4class-<0.20",
        "reference": "simulated",
        "features": "24-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.428",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "P5",
        "protocol": "holdout-test",
        "reference": "simulated",
        "features": "23-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.893",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "P5",
        "protocol": "holdout-domain-Tset>48",
        "reference": "simulated",
        "features": "23-col",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.896",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "P5",
        "protocol": "holdout-test",
        "reference": "simulated",
        "features": "residuals",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.823",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "P5",
        "protocol": "holdout-domain-Tset>48",
        "reference": "simulated",
        "features": "residuals",
        "model": "random-forest",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.764",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X2",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.602",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X2",
        "protocol": "LOMO",
        "reference": "target-machine",
        "features": "residuals",
        "model": "rule-table",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.365",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X2",
        "protocol": "majority-class",
        "reference": "none",
        "features": "",
        "model": "baseline",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.251",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO-calibration-n10",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.377",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO-calibration-n10",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "f1",
        "value": "0.324",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO-calibration-n50",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "accuracy",
        "value": "0.456",
        "n": "10",
        "note": "toy",
    },
    {
        "experiment": "X1",
        "protocol": "LOMO-calibration-n50",
        "reference": "target-machine",
        "features": "residuals",
        "model": "gradient-boosting",
        "label": "__global__",
        "metric": "f1",
        "value": "0.380",
        "n": "10",
        "note": "toy",
    },
]


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _toy_client(tmp_path: Path, rows: list[dict] | None = None) -> TestClient:
    csv_path = tmp_path / "results.csv"
    _write_csv(csv_path, rows if rows is not None else TOY_ROWS)
    confusion = tmp_path / "confusion_matrix.csv"
    confusion.write_text(
        ",A,B\nA,0.9,0.1\nB,0.2,0.8\n",
        encoding="utf-8",
    )
    app = create_app(
        Settings(
            classifier_path=tmp_path / "absent.joblib",
            metadata_path=tmp_path / "absent.json",
            dataset_path=tmp_path / "absent.csv",
            results_path=csv_path,
            confusion_path=confusion,
        )
    )
    return TestClient(app)


def test_evidence_routes_on_toy_csv_without_joblib(tmp_path):
    with _toy_client(tmp_path) as client:
        summary = client.get("/api/evidence/summary")
        assert summary.status_code == 200
        body = summary.json()
        assert body["n_measurements"] == len(TOY_ROWS)
        assert body["headline_value"] == 0.893
        assert body["headline_protocol"]["protocol"] == "holdout-test"

        ladder = client.get("/api/evidence/ladder")
        assert ladder.status_code == 200
        rungs = ladder.json()["rungs"]
        assert [round(r["value"], 3) for r in rungs] == [0.996, 0.919, 0.893, 0.602, 0.454, 0.318, 0.251]
        assert rungs[0]["band"] == "simulator"
        assert rungs[-1]["majority"] is True

        protocols = client.get("/api/evidence/protocols")
        assert protocols.status_code == 200
        series = {row["features"]: row for row in protocols.json()["series"]}
        assert series["residuals"]["random_cv"] == 0.937
        assert series["residuals"]["lomo"] == 0.602
        assert series["raw"]["lomo"] == 0.333

        refs = client.get("/api/evidence/references")
        assert refs.status_code == 200
        payload = refs.json()
        assert payload["majority"] == 0.251
        assert payload["annotation_dmin0"]["accuracy"] == 0.602
        assert payload["annotation_dmin05"]["accuracy"] == 0.482
        assert payload["points"][0]["facet"] == "knn-k5"

        per_class = client.get("/api/evidence/per-class")
        assert per_class.status_code == 200
        rows = {row["display"]: row for row in per_class.json()["rows"]}
        assert rows["Overcharge"]["simulated"] == 0.936
        assert rows["Overcharge"]["target"] == 0.674
        assert rows["Overcharge"]["transferred"] == 0.786
        assert rows["Evap_Airflow"]["simulated"] is None
        assert rows["LiquidLine"]["target"] == 0.04

        runs = client.get("/api/evidence/runs", params={"experiment": "X0", "limit": 10})
        assert runs.status_code == 200
        assert runs.json()["total"] == 3
        assert len(runs.json()["rows"]) == 3

        confusion = client.get("/api/evidence/confusion")
        assert confusion.status_code == 200
        assert confusion.json()["labels"] == ["A", "B"]
        assert confusion.json()["matrix"][0][0] == 0.9

        missing = client.get("/api/evidence/confusion", params={"protocol": "sim2real"})
        assert missing.status_code == 404

        domain = client.get("/api/evidence/domain")
        assert domain.status_code == 200
        assert domain.json()["domain"][0]["accuracy"] == 0.919
        assert domain.json()["severity"][0]["multiclass"] == 0.428

        features = client.get("/api/evidence/features")
        assert features.status_code == 200
        by_feat = {row["features"]: row for row in features.json()["series"]}
        assert by_feat["23-col"]["holdout"] == 0.893
        assert by_feat["residuals"]["domain"] == 0.764

        rules = client.get("/api/evidence/rules")
        assert rules.status_code == 200
        assert rules.json()["majority"] == 0.251
        labels = {row["model"]: row["accuracy"] for row in rules.json()["bars"]}
        assert labels["gradient-boosting"] == 0.602
        assert labels["rule-table"] == 0.365

        calibration = client.get("/api/evidence/calibration")
        assert calibration.status_code == 200
        by_n = {row["n_label"]: row["accuracy"] for row in calibration.json()["points"]}
        assert by_n["0"] == 0.318
        assert by_n["10"] == 0.377
        assert by_n["50"] == 0.456
        assert by_n["all"] == 0.602


def test_evidence_404_when_results_csv_is_absent(tmp_path):
    app = create_app(
        Settings(
            classifier_path=tmp_path / "absent.joblib",
            metadata_path=tmp_path / "absent.json",
            dataset_path=tmp_path / "absent.csv",
            results_path=tmp_path / "missing.csv",
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/evidence/summary")
    assert response.status_code == 404
    assert "results.csv" in response.json()["detail"]


def test_evidence_openapi_tag_and_operation_ids():
    from api.app import app

    spec = TestClient(app).get("/openapi.json").json()
    assert {tag["name"] for tag in spec["tags"]} >= {"inference", "dashboard", "thermo", "evidence"}
    for path in (
        "/api/evidence/summary",
        "/api/evidence/ladder",
        "/api/evidence/protocols",
        "/api/evidence/references",
        "/api/evidence/per-class",
        "/api/evidence/runs",
        "/api/evidence/confusion",
        "/api/evidence/domain",
        "/api/evidence/features",
        "/api/evidence/rules",
        "/api/evidence/calibration",
    ):
        op = spec["paths"][path]["get"]
        assert op["operationId"]
        assert "evidence" in op["tags"]


def test_evidence_reads_shipped_csv_without_joblib(tmp_path):
    from pathlib import Path

    shipped = Path("outputs/results.csv")
    if not shipped.exists():
        pytest.skip("no shipped results.csv")
    app = create_app(
        Settings(
            classifier_path=tmp_path / "absent.joblib",
            metadata_path=tmp_path / "absent.json",
            dataset_path=tmp_path / "absent.csv",
            results_path=shipped,
        )
    )
    with TestClient(app) as client:
        ladder = client.get("/api/evidence/ladder")
        summary = client.get("/api/evidence/summary")
    assert ladder.status_code == 200
    assert summary.status_code == 200
    assert len(ladder.json()["rungs"]) >= 6
    assert summary.json()["headline_value"] is not None


def test_every_logged_experiment_has_a_figure():
    from api.routers.evidence import EXCLUDED_FROM_FIGURES, covered_experiments
    from tools.results import get

    canonical = {"X0", "X0b", "X1", "X2", "X3", "X4", "X5", "P5"}
    logged = {row["experiment"] for row in get()}
    selected = covered_experiments()
    missing = sorted(canonical - selected)
    absent = sorted(canonical - logged)
    assert not missing, f"canonical experiments with no figure: {missing}"
    assert not absent, f"canonical experiments missing from results.csv: {absent}"
    assert EXCLUDED_FROM_FIGURES == {"X3-prelim"}
    assert "X3-prelim" in logged
    assert "X3-prelim" not in selected
    leftover = sorted(logged - selected - EXCLUDED_FROM_FIGURES)
    assert not leftover, f"logged experiments with no figure and no exclusion: {leftover}"
