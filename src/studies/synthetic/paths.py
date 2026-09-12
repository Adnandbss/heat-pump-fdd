"""On-disk layout for the synthetic heating study."""

from pathlib import Path

STUDY = "synthetic"
ROOT = Path(__file__).resolve().parents[3]

OUTPUTS = ROOT / "outputs" / STUDY
MODELS = ROOT / "models" / STUDY

DATASET_PATH = OUTPUTS / "dataset.csv"
COMPARISON_PATH = OUTPUTS / "model_comparison.csv"
CONFUSION_PATH = OUTPUTS / "confusion_matrix.csv"
IMPORTANCE_PATH = OUTPUTS / "feature_importance.csv"
PREDICTIONS_PATH = OUTPUTS / "test_predictions.csv"

CLASSIFIER_PATH = MODELS / "classifier.joblib"
METADATA_PATH = MODELS / "metadata.json"
