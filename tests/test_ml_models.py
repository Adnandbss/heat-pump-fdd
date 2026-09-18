"""The trainer does not import the synthetic study — and the Pipeline actually runs."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.fdd.ml_models import FDDClassifier, FDDPipeline, ModelResults


def test_ml_models_does_not_import_the_data_generator():
    text = Path("src/fdd/ml_models.py").read_text(encoding="utf-8")
    assert "data_generator" not in text
    assert "FaultDataGenerator" not in text
    assert 'if __name__ == "__main__"' not in text


def test_classifier_wraps_scaler_and_clf():
    clf = FDDClassifier(model_type="random_forest", random_state=0)
    assert isinstance(clf.model, Pipeline)
    assert list(clf.model.named_steps) == ["scaler", "clf"]


def test_fit_predict_save_load_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=80), "b": rng.normal(size=80)})
    y = pd.Series(np.where(X["a"] + X["b"] > 0, "A", "B"))
    clf = FDDClassifier(model_type="random_forest", random_state=0)
    clf._estimator.set_params(n_jobs=1, n_estimators=20)
    clf.fit(X, y)
    pred = clf.predict(X)
    assert set(pred) <= {"A", "B"}
    path = tmp_path / "clf.joblib"
    clf.save(path)
    loaded = FDDClassifier.load(path)
    np.testing.assert_array_equal(loaded.predict(X), pred)


def _stub(f1: float) -> ModelResults:
    return ModelResults(
        model_name="x",
        accuracy=f1,
        precision_macro=f1,
        recall_macro=f1,
        f1_macro=f1,
        confusion_matrix=np.zeros((2, 2)),
        classification_report="",
        feature_importance=None,
        roc_curves=None,
        cv_scores=None,
        predictions=np.array([]),
        probabilities=None,
        n=875,
    )


def test_selection_uses_val_and_breaks_ties_on_random_forest():
    pipe = FDDPipeline(random_state=0)
    pipe.val_results = {
        "Random Forest": _stub(0.910),
        "Gradient Boosting": _stub(0.912),
    }
    assert pipe._select_on_val(tie_eps=0.01, n_val=875) == "Random Forest"

    pipe.val_results = {
        "Random Forest": _stub(0.80),
        "Gradient Boosting": _stub(0.95),
    }
    assert pipe._select_on_val(tie_eps=0.01, n_val=875) == "Gradient Boosting"


def test_calibrated_gb_fits_inside_the_pipeline():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=90), "b": rng.normal(size=90)})
    y = pd.Series(["A"] * 45 + ["B"] * 45)
    clf = FDDClassifier(model_type="gradient_boosting", random_state=0)
    clf.fit(X, y, calibrate=True, tune=False)
    proba = clf.predict_proba(X)
    assert proba.shape == (90, 2)
    assert abs(proba.sum(axis=1) - 1).max() < 1e-6
