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
import warnings

import joblib
from sklearn.model_selection import (
    cross_val_score, GridSearchCV, StratifiedKFold
)
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
        
        # Encoder les labels
        y_encoded = self.label_encoder.fit_transform(y)
        self.class_names = list(self.label_encoder.classes_)
        
        # Normaliser
        X_scaled = self.scaler.fit_transform(X)
        
        # SMOTE si demandé
        if use_smote and IMBALANCED_AVAILABLE:
            smote = SMOTE(random_state=self.random_state)
            X_scaled, y_encoded = smote.fit_resample(X_scaled, y_encoded)
        
        weights = compute_sample_weight("balanced", y_encoded)

        if tune and self.model_type == "gradient_boosting":
            grid = GridSearchCV(
                GradientBoostingClassifier(random_state=self.random_state),
                {
                    "n_estimators": [120, 180],
                    "max_depth": [3, 5],
                    "learning_rate": [0.05, 0.1],
                },
                cv=3,
                scoring="f1_macro",
                n_jobs=-1,
            )
            grid.fit(X_scaled, y_encoded, sample_weight=weights)
            self.model = grid.best_estimator_
            print(f"    Best GB params: {grid.best_params_} (cv F1={grid.best_score_:.3f})")
        else:
            fit_kwargs = {}
            if self.model_type == "gradient_boosting":
                fit_kwargs["sample_weight"] = weights
            self.model.fit(X_scaled, y_encoded, **fit_kwargs)

        if calibrate:
            self.model = CalibratedClassifierCV(
                self.model, method="sigmoid", cv=3
            )
            self.model.fit(X_scaled, y_encoded)
        
        self.is_fitted = True
        
        return self
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Prédit les classes pour de nouvelles données."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        X_subset = X[self.feature_names] if self.feature_names else X
        X_scaled = self.scaler.transform(X_subset)
        
        y_pred_encoded = self.model.predict(X_scaled)
        return self.label_encoder.inverse_transform(y_pred_encoded)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Retourne les probabilités de chaque classe."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        
        X_subset = X[self.feature_names] if self.feature_names else X
        X_scaled = self.scaler.transform(X_subset)
        
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X_scaled)
        else:
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
        except:
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
            probabilities=y_proba
        )
    
    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        cv: int = 5,
        feature_columns: Optional[List[str]] = None
    ) -> Tuple[float, float]:
        """
        Effectue une validation croisée.
        
        Returns:
        --------
        Tuple (mean_score, std_score)
        """
        if feature_columns:
            X = X[feature_columns]
        
        X_scaled = self.scaler.fit_transform(X)
        y_encoded = self.label_encoder.fit_transform(y)
        
        cv_splitter = StratifiedKFold(
            n_splits=cv, shuffle=True, random_state=self.random_state
        )
        
        scores = cross_val_score(
            self.model, X_scaled, y_encoded,
            cv=cv_splitter, scoring='f1_macro'
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
                if inner is not None and hasattr(inner, "feature_importances_"):
                    inner_imps.append(inner.feature_importances_)
            if inner_imps:
                importance = np.mean(inner_imps, axis=0)
        elif hasattr(est, "feature_importances_"):
            importance = est.feature_importances_
        elif self.model_type == 'ensemble':
            # Moyenne des importances de l'ensemble
            importances = []
            for name, est in self.model.named_estimators_.items():
                if hasattr(est, 'feature_importances_'):
                    importances.append(est.feature_importances_)
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
        
        X_scaled = self.scaler.fit_transform(X)
        y_encoded = self.label_encoder.fit_transform(y)
        
        # Grilles de paramètres par type de modèle
        param_grids = {
            'random_forest': {
                'n_estimators': [50, 100, 200],
                'max_depth': [5, 10, 15, None],
                'min_samples_split': [2, 5, 10]
            },
            'svm': {
                'C': [0.1, 1, 10, 100],
                'gamma': ['scale', 'auto', 0.01, 0.1],
                'kernel': ['rbf', 'poly']
            },
            'xgboost': {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1, 0.2]
            },
            'gradient_boosting': {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1, 0.2]
            }
        }
        
        if self.model_type not in param_grids:
            return {}
        
        grid_search = GridSearchCV(
            self.model,
            param_grids[self.model_type],
            cv=cv,
            scoring='f1_macro',
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X_scaled, y_encoded)
        
        # Mettre à jour le modèle
        self.model = grid_search.best_estimator_
        
        return {
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_
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
        self.best_model = None
    
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
        X_test: pd.DataFrame,
        y_test: pd.Series,
        feature_columns: List[str]
    ) -> Dict[str, ModelResults]:
        """
        Entraîne et évalue tous les modèles.
        
        Returns:
        --------
        Dict[model_name -> ModelResults]
        """
        for name, model in self.models.items():
            print(f"\n>>> Entraînement de {name}...")
            
            # Entraîner
            tune = name == "Gradient Boosting"
            model.fit(
                X_train,
                y_train,
                feature_columns=feature_columns,
                tune=tune,
                calibrate=tune,
            )
            
            # Évaluer
            results = model.evaluate(X_test, y_test)
            self.results[name] = results
            
            print(f"    Accuracy: {results.accuracy:.4f}")
            print(f"    F1 Macro: {results.f1_macro:.4f}")
        
        # Trouver le meilleur modèle
        best_name = max(self.results.keys(), key=lambda k: self.results[k].f1_macro)
        self.best_model = self.models[best_name]
        
        print(f"\n>>> Meilleur modèle: {best_name} (F1={self.results[best_name].f1_macro:.4f})")
        
        return self.results
    
    def get_comparison_table(self) -> pd.DataFrame:
        """Retourne un tableau comparatif des modèles."""
        data = []
        for name, result in self.results.items():
            data.append({
                'Model': name,
                'Accuracy': result.accuracy,
                'Precision': result.precision_macro,
                'Recall': result.recall_macro,
                'F1 Score': result.f1_macro
            })
        
        df = pd.DataFrame(data)
        return df.sort_values('F1 Score', ascending=False).reset_index(drop=True)

