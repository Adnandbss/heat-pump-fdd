"""Synthetic-study artefacts live under outputs/<study> and models/<study>."""

from src.fdd.inference import DEFAULT_METADATA_PATH, DEFAULT_MODEL_PATH
from src.studies.synthetic.paths import (
    CLASSIFIER_PATH,
    DATASET_PATH,
    METADATA_PATH,
    OUTPUTS,
    STUDY,
)


def test_study_constant_is_synthetic():
    assert STUDY == "synthetic"
    assert OUTPUTS.name == STUDY
    assert DATASET_PATH.name == "dataset.csv"


def test_shipped_artefacts_exist():
    assert CLASSIFIER_PATH.is_file()
    assert METADATA_PATH.is_file()
    assert DATASET_PATH.is_file()


def test_engine_defaults_follow_the_synthetic_layout():
    assert DEFAULT_MODEL_PATH == CLASSIFIER_PATH
    assert DEFAULT_METADATA_PATH == METADATA_PATH


def test_metadata_describes_the_study():
    import json

    meta = json.loads(METADATA_PATH.read_text())
    assert meta["study"] == "synthetic"
    assert meta["mode"] == "heating"
    assert meta["source"] == "simulator"
    assert meta["taxonomy"] == "project-7class"
