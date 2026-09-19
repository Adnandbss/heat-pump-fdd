"""Integrity of `outputs/results.csv`, the single source of measured numbers."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.results import COLUMNS, RESULTS_PATH, _KEY

BOUNDED = {"accuracy", "f1", "precision", "recall"}


def _rows():
    if not RESULTS_PATH.exists():
        pytest.skip("no results logged yet")
    with RESULTS_PATH.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_schema_is_intact():
    if not RESULTS_PATH.exists():
        pytest.skip("no results logged yet")
    with RESULTS_PATH.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == COLUMNS, f"unexpected columns: {header}"


def test_every_number_names_its_protocol():
    for r in _rows():
        assert r["protocol"], f"row without protocol: {r}"
        assert r["reference"], f"row without healthy-reference source: {r}"


def test_no_duplicate_measurement():
    seen = {}
    for r in _rows():
        key = tuple(r[c] for c in _KEY)
        assert key not in seen, (
            f"the same measurement is logged twice with different values: "
            f"{key} -> {seen.get(key)} and {r['value']}"
        )
        seen[key] = r["value"]


def test_bounded_metrics_are_in_range():
    for r in _rows():
        if r["metric"] in BOUNDED:
            v = float(r["value"])
            assert 0.0 <= v <= 1.0, f"{r['metric']} out of range: {r}"


def test_p5_logged_four_contracts_on_two_protocols():
    """The P5 decision is the comparative table — it must be in results.csv."""
    rows = [
        r for r in _rows()
        if r["experiment"] == "P5" and r["metric"] == "accuracy" and r["label"] == "__global__"
    ]
    protocols = {r["protocol"] for r in rows}
    features = {r["features"] for r in rows}
    assert protocols >= {"holdout-test", "holdout-domain-Tset>48"}
    assert features >= {"23-col", "residuals+conditions", "residuals", "23-col-minus-dead"}
    assert len(rows) >= 8


def test_log_replaces_atomically(tmp_path, monkeypatch):
    from tools import results as results_mod

    path = tmp_path / "results.csv"
    monkeypatch.setattr(results_mod, "RESULTS_PATH", path)
    results_mod.log(
        experiment="T", protocol="holdout", reference="sim",
        metric="accuracy", value=0.5, n=10,
    )
    results_mod.log(
        experiment="T", protocol="holdout", reference="sim",
        metric="accuracy", value=0.6, n=10,
    )
    rows = results_mod.get(experiment="T", metric="accuracy")
    assert len(rows) == 1
    assert float(rows[0]["value"]) == pytest.approx(0.6)
