"""
Modèles de Machine Learning pour FDD (Fault Detection & Diagnostics)
=====================================================================

Ce module implémente plusieurs algorithmes de classification pour
la détection et le diagnostic de défauts sur pompes à chaleur.

Algorithmes disponibles:
- Random Forest (baseline robuste)
- Gradient Boosting (GridSearch + calibration des probabilités)

Fonctionnalités:
- Entraînement avec validation croisée
- Optimisation des hyperparamètres
- Évaluation multi-métrique
- Analyse d'importance des features
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

import joblib
from sklearn.base import clone
from sklearn.model_selection import (
    cross_val_score, GridSearchCV, StratifiedKFold
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import (
    RandomForestClassifier, VotingClassifier, GradientBoostingClassifier
)
from sklearn.svm import SVC
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    precision_score, recall_score, f1_score, roc_auc_score,
    roc_curve, precision_recall_curve, average_precision_score
)
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.calibration import CalibratedClassifierCV

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except Exception:
    XGBOOST_AVAILABLE = False
    XGBClassifier = None

try:
    from imblearn.over_sampling import SMOTE
    IMBALANCED_AVAILABLE = True
except ImportError:
    IMBALANCED_AVAILABLE = False


def wilson_ci(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """95 % Wilson interval for a binomial proportion."""
    if n <= 0:
        return 0.0, 1.0
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    half = z * np.sqrt((p * (1.0 - p) / n) + z2 / (4.0 * n * n)) / denom
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def _pipeline_classifier(est):
    """Unwrap a Pipeline to its ``clf`` step; otherwise return ``est``."""
    if est is not None and hasattr(est, "named_steps") and "clf" in est.named_steps:
        return est.named_steps["clf"]
    return est


@dataclass
class ModelResults:
    """Résultats d'évaluation d'un modèle."""
    model_name: str
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    confusion_matrix: np.ndarray
    classification_report: str
    feature_importance: Optional[pd.DataFrame]
    roc_curves: Optional[Dict]
    cv_scores: Optional[np.ndarray]
    predictions: np.ndarray
    probabilities: Optional[np.ndarray]
    n: int = 0
    accuracy_ci_low: float = 0.0
    accuracy_ci_high: float = 1.0
    split: str = "test"
    class_names: Optional[List[str]] = None


class FDDClassifier:
    """
    Classificateur de défauts pour pompes à chaleur.
    
    Cette classe encapsule plusieurs modèles de ML et fournit
    une interface unifiée pour l'entraînement, l'évaluation et
    la prédiction.
    
    Parameters:
    -----------
    model_type : str
        Type de modèle ('random_forest', 'svm', 'xgboost', 'ensemble')
    random_state : int
        Graine pour reproductibilité
    """
    
    AVAILABLE_MODELS = ['random_forest', 'svm', 'xgboost', 'ensemble', 'gradient_boosting']
    
    def __init__(
        self,
        model_type: str = 'random_forest',
        random_state: int = 42
    ):
        if model_type not in self.AVAILABLE_MODELS:
            raise ValueError(f"Model type must be one of {self.AVAILABLE_MODELS}")
        
        if model_type == 'xgboost' and not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost is not installed")
        
        self.model_type = model_type
        self.random_state = random_state
        
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.model = None
        self.is_fitted = False
        
        self.feature_names = None
        self.class_names = None
        
        self._init_model()
    
    def _init_model(self):
        """Initialise le modèle selon le type choisi."""
        
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight='balanced',
                random_state=self.random_state,
                n_jobs=-1
            )
        
        elif self.model_type == 'svm':
            self.model = SVC(
                kernel='rbf',
                C=10.0,
                gamma='scale',
                class_weight='balanced',
                probability=True,
                random_state=self.random_state
            )
        
        elif self.model_type == 'xgboost':
            self.model = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
                use_label_encoder=False,
                eval_metric='mlogloss'
            )
        
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=self.random_state
            )
        
        elif self.model_type == 'ensemble':
            estimators = [
                ('rf', RandomForestClassifier(
                    n_estimators=50, max_depth=10,
                    random_state=self.random_state, n_jobs=-1
                )),
                ('gb', GradientBoostingClassifier(
                    n_estimators=50, max_depth=4,
                    random_state=self.random_state
                )),
            ]
            if XGBOOST_AVAILABLE:
                estimators.append(
                    ('xgb', XGBClassifier(
                        n_estimators=50, max_depth=4,
                        random_state=self.random_state,
                        use_label_encoder=False,
                        eval_metric='mlogloss'
                    ))
                )
            
            self.model = VotingClassifier(
                estimators=estimators,
                voting='soft'
            )

        self._estimator = self.model
        self.model = self._make_pipeline(clone(self._estimator))

    def _make_pipeline(self, estimator=None) -> Pipeline:
        est = clone(estimator) if estimator is not None else clone(self._estimator)
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", est),
        ])

    def _model_includes_scaler(self) -> bool:
        m = self.model
        if isinstance(m, Pipeline) and "scaler" in getattr(m, "named_steps", {}):
            return True
        if isinstance(m, CalibratedClassifierCV):
            inner = getattr(m, "estimator", None)
            if isinstance(inner, Pipeline) and "scaler" in inner.named_steps:
                return True
            cals = getattr(m, "calibrated_classifiers_", None)
            if cals:
                est = getattr(cals[0], "estimator", None)
                if isinstance(est, Pipeline):
                    return True
        return False

    def _features_frame(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.feature_names:
            return X[self.feature_names]
        return X
    
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_columns: Optional[List[str]] = None,
        use_smote: bool = False,
        tune: bool = False,
        calibrate: bool = False,
    ) -> 'FDDClassifier':
        """
        Entraîne le modèle sur les données.
        
        Parameters:
        -----------
        X : pd.DataFrame
            Features d'entraînement
        y : pd.Series
            Labels
        feature_columns : List[str], optional
            Colonnes à utiliser comme features
        use_smote : bool
            Utiliser SMOTE pour le rééquilibrage
        
        Returns:
        --------
        self
        """
        # Sélectionner les features
        if feature_columns:
            X = X[feature_columns].copy()
        
        self.feature_names = list(X.columns)

        y_encoded = self.label_encoder.fit_transform(y)
        self.class_names = list(self.label_encoder.classes_)

        X_fit = X
        if use_smote and IMBALANCED_AVAILABLE:
            smote = SMOTE(random_state=self.random_state)
            X_res, y_encoded = smote.fit_resample(X, y_encoded)
            X_fit = pd.DataFrame(X_res, columns=self.feature_names)

        weights = compute_sample_weight("balanced", y_encoded)
        pipe = self._make_pipeline(clone(self._estimator))

        if tune and self.model_type == "gradient_boosting":
            grid = GridSearchCV(
                pipe,
                {
                    "clf__n_estimators": [120, 180],
                    "clf__max_depth": [3, 5],
                    "clf__learning_rate": [0.05, 0.1],
                },
                cv=3,
                scoring="f1_macro",
                n_jobs=-1,
            )
            grid.fit(X_fit, y_encoded, clf__sample_weight=weights)
            pipe = grid.best_estimator_
            print(f"    Best GB params: {grid.best_params_} (cv F1={grid.best_score_:.3f})")
        else:
            fit_kwargs = {}
            if self.model_type == "gradient_boosting":
                fit_kwargs["clf__sample_weight"] = weights
            pipe.fit(X_fit, y_encoded, **fit_kwargs)

        if calibrate:
            # Pipeline has no `sample_weight` arg; route weights to the
            # classifier step so calibration refits the same weighted GB.
            self.model = CalibratedClassifierCV(pipe, method="sigmoid", cv=3)
            self.model.fit(X_fit, y_encoded, clf__sample_weight=weights)
        else:
            self.model = pipe

        if isinstance(self.model, Pipeline):
            self.scaler = self.model.named_steps["scaler"]
        elif isinstance(self.model, CalibratedClassifierCV) and isinstance(
            getattr(self.model, "estimator", None), Pipeline
        ):
            self.scaler = self.model.estimator.named_steps["scaler"]

        self.is_fitted = True
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Prédit les classes pour de nouvelles données."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        X_subset = self._features_frame(X)
        X_in = X_subset if self._model_includes_scaler() else self.scaler.transform(X_subset)
        y_pred_encoded = self.model.predict(X_in)
        return self.label_encoder.inverse_transform(y_pred_encoded)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Retourne les probabilités de chaque classe."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        X_subset = self._features_frame(X)
        X_in = X_subset if self._model_includes_scaler() else self.scaler.transform(X_subset)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X_in)
        raise AttributeError("Model does not support probability estimation")
    
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        compute_roc: bool = True
    ) -> ModelResults:
        """
        Évalue le modèle sur un jeu de test.
        
        Parameters:
        -----------
        X_test : pd.DataFrame
            Features de test
        y_test : pd.Series
            Labels de test
        compute_roc : bool
            Calculer les courbes ROC
        
        Returns:
        --------
        ModelResults avec toutes les métriques
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before evaluation")
        
        # Prédictions
        y_pred = self.predict(X_test)
        y_test_array = np.array(y_test)
        
        # Probabilités si disponibles
        try:
            y_proba = self.predict_proba(X_test)
        except Exception:
            y_proba = None
        
        # Métriques de base
        accuracy = accuracy_score(y_test_array, y_pred)
        precision = precision_score(y_test_array, y_pred, average='macro', zero_division=0)
        recall = recall_score(y_test_array, y_pred, average='macro', zero_division=0)
        f1 = f1_score(y_test_array, y_pred, average='macro', zero_division=0)
        
        # Matrice de confusion
        cm = confusion_matrix(y_test_array, y_pred, labels=self.class_names)
        
        # Rapport de classification
        report = classification_report(
            y_test_array, y_pred,
            target_names=self.class_names,
            zero_division=0
        )
        
        # Importance des features
        feature_importance = self._get_feature_importance()
        
        # Courbes ROC
        roc_curves = None
        if compute_roc and y_proba is not None and len(self.class_names) > 2:
            roc_curves = self._compute_roc_curves(y_test, y_proba)

        n = len(y_test_array)
        acc_lo, acc_hi = wilson_ci(float(accuracy), n)

        return ModelResults(
            model_name=self.model_type,
            accuracy=accuracy,
            precision_macro=precision,
            recall_macro=recall,
            f1_macro=f1,
            confusion_matrix=cm,
            classification_report=report,
            feature_importance=feature_importance,
            roc_curves=roc_curves,
            cv_scores=None,
            predictions=y_pred,
            probabilities=y_proba,
            n=n,
            accuracy_ci_low=acc_lo,
            accuracy_ci_high=acc_hi,
            class_names=list(self.class_names) if self.class_names is not None else None,
        )
    
    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        cv: int = 5,
        feature_columns: Optional[List[str]] = None
    ) -> Tuple[float, float]:
        """Stratified CV of a fresh scaler+classifier pipeline.

        The estimator is cloned: a fitted classifier is not reused, and the
        scaler is fit on each training fold only. Pass ``X_train`` — never the
        full dataset, and never the test split.

        Returns
        -------
        Tuple[float, float]
            Mean and std of fold F1-macro scores.
        """
        if feature_columns:
            X = X[feature_columns]

        encoder = LabelEncoder()
        y_encoded = encoder.fit_transform(y)
        pipe = self._make_pipeline(clone(self._estimator))
        cv_splitter = StratifiedKFold(
            n_splits=cv, shuffle=True, random_state=self.random_state
        )
        scores = cross_val_score(
            pipe, X, y_encoded,
            cv=cv_splitter, scoring="f1_macro",
        )
        return scores.mean(), scores.std()
    
    def _get_feature_importance(self) -> Optional[pd.DataFrame]:
        """Extrait l'importance des features du modèle."""
        if not self.is_fitted or not self.feature_names:
            return None
        
        importance = None
        est = self.model
        if hasattr(est, "calibrated_classifiers_"):
            inner_imps = []
            for calibrated in est.calibrated_classifiers_:
                inner = getattr(calibrated, "estimator", None) or getattr(
                    calibrated, "base_estimator", None
                )
                inner = _pipeline_classifier(inner)
                if inner is not None and hasattr(inner, "feature_importances_"):
                    inner_imps.append(inner.feature_importances_)
            if inner_imps:
                importance = np.mean(inner_imps, axis=0)
        else:
            inner = _pipeline_classifier(est)
            if inner is not None and hasattr(inner, "feature_importances_"):
                importance = inner.feature_importances_
            elif self.model_type == "ensemble":
                importances = []
                voting = _pipeline_classifier(est)
                named = getattr(voting, "named_estimators_", {})
                for _name, sub in named.items():
                    if hasattr(sub, "feature_importances_"):
                        importances.append(sub.feature_importances_)
                if importances:
                    importance = np.mean(importances, axis=0)
        
        if importance is not None:
            df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': importance
            })
            return df.sort_values('importance', ascending=False).reset_index(drop=True)
        
        return None
    
    def _compute_roc_curves(
        self,
        y_test: pd.Series,
        y_proba: np.ndarray
    ) -> Dict:
        """Calcule les courbes ROC pour chaque classe."""
        roc_curves = {}
        
        # Binariser y_test
        y_test_encoded = self.label_encoder.transform(y_test)
        
        for i, class_name in enumerate(self.class_names):
            y_binary = (y_test_encoded == i).astype(int)
            
            if y_proba.shape[1] > i:
                fpr, tpr, thresholds = roc_curve(y_binary, y_proba[:, i])
                auc = roc_auc_score(y_binary, y_proba[:, i])
                
                roc_curves[class_name] = {
                    'fpr': fpr,
                    'tpr': tpr,
                    'thresholds': thresholds,
                    'auc': auc
                }
        
        return roc_curves
    
    def optimize_hyperparameters(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_columns: Optional[List[str]] = None,
        cv: int = 3
    ) -> Dict[str, Any]:
        """
        Optimise les hyperparamètres par Grid Search.
        
        Returns:
        --------
        Dict avec les meilleurs paramètres
        """
        if feature_columns:
            X = X[feature_columns]

        y_encoded = self.label_encoder.fit_transform(y)
        self.class_names = list(self.label_encoder.classes_)
        self.feature_names = list(X.columns)

        param_grids = {
            "random_forest": {
                "clf__n_estimators": [50, 100, 200],
                "clf__max_depth": [5, 10, 15, None],
                "clf__min_samples_split": [2, 5, 10],
            },
            "svm": {
                "clf__C": [0.1, 1, 10, 100],
                "clf__gamma": ["scale", "auto", 0.01, 0.1],
                "clf__kernel": ["rbf", "poly"],
            },
            "xgboost": {
                "clf__n_estimators": [50, 100, 200],
                "clf__max_depth": [3, 5, 7],
                "clf__learning_rate": [0.01, 0.1, 0.2],
            },
            "gradient_boosting": {
                "clf__n_estimators": [50, 100, 200],
                "clf__max_depth": [3, 5, 7],
                "clf__learning_rate": [0.01, 0.1, 0.2],
            },
        }

        if self.model_type not in param_grids:
            return {}

        pipe = self._make_pipeline(clone(self._estimator))
        grid_search = GridSearchCV(
            pipe,
            param_grids[self.model_type],
            cv=cv,
            scoring="f1_macro",
            n_jobs=-1,
            verbose=1,
        )
        grid_search.fit(X, y_encoded)
        self.model = grid_search.best_estimator_
        if isinstance(self.model, Pipeline):
            self.scaler = self.model.named_steps["scaler"]
        self.is_fitted = True

        return {
            "best_params": grid_search.best_params_,
            "best_score": grid_search.best_score_,
            "cv_results": grid_search.cv_results_,
        }

    def save(self, path: str) -> None:
        """Serialize the fitted classifier, scaler and label encoder."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model")
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "label_encoder": self.label_encoder,
                "feature_names": self.feature_names,
                "class_names": self.class_names,
                "model_type": self.model_type,
                "random_state": self.random_state,
                "uses_pipeline": True,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "FDDClassifier":
        """Load a classifier saved with ``save``."""
        payload = joblib.load(path)
        obj = cls.__new__(cls)
        obj.model_type = payload["model_type"]
        obj.random_state = payload.get("random_state", 42)
        obj.model = payload["model"]
        obj.scaler = payload["scaler"]
        obj.label_encoder = payload["label_encoder"]
        obj.feature_names = payload["feature_names"]
        obj.class_names = payload["class_names"]
        obj.is_fitted = True
        inner = obj.model
        if isinstance(inner, CalibratedClassifierCV):
            inner = getattr(inner, "estimator", inner)
        inner = _pipeline_classifier(inner)
        try:
            obj._estimator = clone(inner)
        except Exception:
            obj._estimator = inner
        return obj


class FDDPipeline:
    """
    Pipeline complet pour FDD incluant prétraitement et multi-modèles.
    
    Cette classe facilite la comparaison de plusieurs algorithmes
    et la sélection du meilleur modèle.
    """
    
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.models = {}
        self.results = {}
        self.val_results = {}
        self.best_model = None
        self.best_model_name = None
    
    def add_model(self, name: str, model_type: str) -> 'FDDPipeline':
        """Ajoute un modèle au pipeline."""
        self.models[name] = FDDClassifier(
            model_type=model_type,
            random_state=self.random_state
        )
        return self
    
    def add_all_models(self) -> 'FDDPipeline':
        """Ajoute tous les modèles disponibles."""
        self.add_model('Random Forest', 'random_forest')
        self.add_model('Gradient Boosting', 'gradient_boosting')
        return self
    
    def fit_evaluate_all(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        feature_columns: List[str],
        tie_eps: float = 0.01,
    ) -> Dict[str, ModelResults]:
        """Fit on train, select on val, report test. Never select on test."""
        for name, model in self.models.items():
            print(f"\n>>> Entraînement de {name}...")
            tune = name == "Gradient Boosting"
            model.fit(
                X_train,
                y_train,
                feature_columns=feature_columns,
                tune=tune,
                calibrate=tune,
            )
            val_res = model.evaluate(X_val, y_val)
            val_res.split = "val"
            test_res = model.evaluate(X_test, y_test)
            test_res.split = "test"
            self.val_results[name] = val_res
            self.results[name] = test_res
            print(
                f"    Val  F1={val_res.f1_macro:.4f}  acc={val_res.accuracy:.4f}  "
                f"[{val_res.accuracy_ci_low:.3f}, {val_res.accuracy_ci_high:.3f}]"
            )
            print(
                f"    Test F1={test_res.f1_macro:.4f}  acc={test_res.accuracy:.4f}  "
                f"[{test_res.accuracy_ci_low:.3f}, {test_res.accuracy_ci_high:.3f}]"
            )

        self.best_model_name = self._select_on_val(tie_eps=tie_eps, n_val=len(y_val))
        self.best_model = self.models[self.best_model_name]
        chosen = self.val_results[self.best_model_name]
        print(
            f"\n>>> Modèle retenu (sélection sur val): {self.best_model_name} "
            f"(val F1={chosen.f1_macro:.4f})"
        )
        return self.results

    def _select_on_val(self, tie_eps: float, n_val: int) -> str:
        ranked = sorted(
            self.val_results.items(),
            key=lambda kv: kv[1].f1_macro,
            reverse=True,
        )
        best_name, best = ranked[0]
        if len(ranked) == 1:
            return best_name
        second_name, second = ranked[1]
        se = np.sqrt(max(best.f1_macro * (1.0 - best.f1_macro), 1e-12) / max(n_val, 1))
        tied = abs(best.f1_macro - second.f1_macro) < max(tie_eps, 2.0 * se)
        if tied:
            # Same score on val: prefer Random Forest — cheaper inference,
            # readable importances, typically stabler than a tuned GB.
            if "Random Forest" in self.val_results:
                print(
                    f"    Égalité val F1 ({best.f1_macro:.4f} vs {second.f1_macro:.4f}); "
                    "départage: Random Forest (interprétabilité / inférence)"
                )
                return "Random Forest"
        return best_name
    
    def get_comparison_table(self) -> pd.DataFrame:
        """Retourne un tableau comparatif des modèles."""
        data = []
        for name, result in self.results.items():
            val = self.val_results.get(name)
            data.append({
                "Model": name,
                "Accuracy": result.accuracy,
                "Precision": result.precision_macro,
                "Recall": result.recall_macro,
                "F1 Score": result.f1_macro,
                "Accuracy_CI_low": result.accuracy_ci_low,
                "Accuracy_CI_high": result.accuracy_ci_high,
                "Val_F1": val.f1_macro if val is not None else np.nan,
                "n_test": result.n,
            })
        df = pd.DataFrame(data)
        if self.best_model_name:
            order = {self.best_model_name: 0}
            df["_sel"] = df["Model"].map(lambda n: order.get(n, 1))
            df = df.sort_values(["_sel", "Val_F1"], ascending=[True, False]).drop(columns="_sel")
        else:
            df = df.sort_values("F1 Score", ascending=False)
        return df.reset_index(drop=True)

