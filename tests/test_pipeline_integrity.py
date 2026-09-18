"""Guards that would have caught the synthetic-study leaks on day one.

A dataset whose labels are decorrelated from the features must score near
chance. Derived columns must match the (noisy) sensors they are computed from.
No residual may be exactly zero on a whole class — that was ``d_COP`` encoding
the detection label.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

import pytest

from src.fdd.features import DEFAULT_CAPACITY_NOM, FEATURE_COLUMNS
from src.fdd.ml_models import FDDClassifier
from src.studies.synthetic.generator import FaultDataGenerator, FaultType, recompute_derived
from src.studies.synthetic.paths import DATASET_PATH


def _small_dataset(n: int = 360, seed: int = 0) -> pd.DataFrame:
    gen = FaultDataGenerator(random_seed=seed)
    distribution = {
        FaultType.NORMAL: 0.40,
        FaultType.CONDENSER_FOULING: 0.15,
        FaultType.EVAPORATOR_FOULING: 0.15,
        FaultType.REFRIGERANT_UNDERCHARGE: 0.10,
        FaultType.CONDENSER_FAN_FAULT: 0.10,
        FaultType.EVAPORATOR_FAN_FAULT: 0.10,
    }
    return gen.generate_dataset(
        n_samples=n, fault_distribution=distribution, show_progress=False
    )


def test_derived_features_are_consistent_with_their_noisy_inputs():
    df = _small_dataset()
    assert np.allclose(df.pressure_ratio, df.P_cond / df.P_evap, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.compression_ratio, df.P_cond / df.P_evap, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.COP, df.Q_cond / df.W_comp, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.delta_T_evap, df.T_ambient - df.T_evap, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.delta_T_cond, df.T_cond - df.T_setpoint, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.capacity_ratio, df.Q_cond / DEFAULT_CAPACITY_NOM, rtol=1e-6, atol=1e-9)


def test_recompute_derived_is_idempotent_on_a_row():
    df = _small_dataset(n=80, seed=1)
    row = df.iloc[0].to_dict()
    before = {
        k: row[k]
        for k in ("COP", "pressure_ratio", "delta_T_evap", "delta_T_cond", "capacity_ratio")
    }
    recompute_derived(row)
    for k, v in before.items():
        assert abs(row[k] - v) < 1e-9


def test_no_residual_is_exactly_zero_on_a_whole_class():
    df = _small_dataset()
    for col in ("d_COP", "d_W_comp", "d_superheat", "d_subcooling", "d_T_discharge"):
        zero_rate = df.groupby("fault_type")[col].apply(lambda s: (s.abs() < 1e-12).mean())
        assert zero_rate.max() < 0.99, f"{col} identifies a class by construction: {zero_rate.to_dict()}"


def test_d_cop_is_not_a_perfect_fault_detector():
    df = _small_dataset()
    X = df[["d_COP"]]
    y = df["is_faulty"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=0, stratify=y
    )
    tree = DecisionTreeClassifier(max_depth=1, random_state=0)
    tree.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, tree.predict(X_te))
    assert acc < 0.99, f"a one-leaf tree on d_COP still separates detection at {acc:.3f}"


def test_shuffled_labels_score_near_majority():
    df = _small_dataset(n=400, seed=2)
    X = df[FEATURE_COLUMNS].reset_index(drop=True)
    y = df["fault_type"].reset_index(drop=True)
    y_shuf = y.sample(frac=1, random_state=0).reset_index(drop=True)
    majority = float(y_shuf.value_counts().max() / len(y_shuf))
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y_shuf, test_size=0.3, random_state=0, stratify=y_shuf
    )
    clf = FDDClassifier(model_type="random_forest", random_state=0)
    clf._estimator.set_params(n_jobs=1, n_estimators=40)
    clf.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, clf.predict(X_te))
    assert acc < majority + 0.18, (
        f"shuffled-label accuracy {acc:.3f} is well above majority {majority:.3f}; "
        "the features still carry the label"
    )


def test_classifier_wraps_scaler_in_a_pipeline():
    clf = FDDClassifier(model_type="random_forest")
    assert isinstance(clf.model, Pipeline)
    assert list(clf.model.named_steps) == ["scaler", "clf"]


def test_committed_dataset_derived_are_consistent():
    if not DATASET_PATH.exists():
        pytest.skip("no committed synthetic dataset")
    df = pd.read_csv(DATASET_PATH)
    assert np.allclose(df.pressure_ratio, df.P_cond / df.P_evap, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.COP, df.Q_cond / df.W_comp, rtol=1e-6, atol=1e-9)
    assert np.allclose(df.capacity_ratio, df.Q_cond / DEFAULT_CAPACITY_NOM, rtol=1e-6, atol=1e-9)
    zero_rate = df.groupby("fault_type")["d_COP"].apply(lambda s: (s.abs() < 1e-12).mean())
    assert zero_rate.max() < 0.99, f"committed dataset still leaks d_COP: {zero_rate.to_dict()}"


def test_generator_fills_the_requested_size_and_counts_rejects():
    gen = FaultDataGenerator(random_seed=0)
    distribution = {
        FaultType.NORMAL: 0.40,
        FaultType.CONDENSER_FOULING: 0.30,
        FaultType.EVAPORATOR_FOULING: 0.30,
    }
    df = gen.generate_dataset(
        n_samples=80, fault_distribution=distribution, show_progress=False
    )
    assert len(df) + gen.n_dropped_nan == 80
    assert gen.n_rejected >= 0


def test_shipped_model_declares_its_provenance():
    import json
    from sklearn import __version__ as sklearn_version
    from src.physics.simulator import HAS_COOLPROP
    from src.studies.synthetic.paths import MODELS

    meta_path = MODELS / "metadata.json"
    if not meta_path.exists():
        pytest.skip("no shipped model metadata")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["sklearn_version"] == sklearn_version
    assert meta["selected_on"] == "val"
    assert meta["n_test"] == 1500
    assert meta["coolprop"] == bool(HAS_COOLPROP)
    assert meta["random_state"] == 42
    assert len(meta.get("dataset_sha256", "")) == 64
    from tools.results import value
    logged = value(
        experiment="X0",
        protocol="holdout-test",
        metric="accuracy",
        model="random-forest",
        label="__global__",
    )
    assert abs(meta["accuracy"] - logged) < 1e-6
