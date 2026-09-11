"""The trainer does not import the synthetic study."""

from pathlib import Path


def test_ml_models_does_not_import_the_data_generator():
    text = Path("src/ml_models.py").read_text(encoding="utf-8")
    assert "data_generator" not in text
    assert "FaultDataGenerator" not in text
    assert 'if __name__ == "__main__"' not in text
