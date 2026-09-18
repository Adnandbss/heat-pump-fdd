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
