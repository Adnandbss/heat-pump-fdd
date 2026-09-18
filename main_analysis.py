"""
==========================================================================
Diagnostic de Pannes par Machine Learning (FDD)
Pompes à Chaleur - Détection et Diagnostic de Défauts
==========================================================================

Ce script exécute une analyse complète de FDD (Fault Detection & Diagnostics)
pour les pompes à chaleur en utilisant des algorithmes de Machine Learning.

Usage:
    python main_analysis.py

Outputs:
    - outputs/synthetic/dataset.csv : Dataset généré
    - outputs/synthetic/model_comparison.csv : Comparaison des modèles
    - outputs/*.png : Visualisations
"""

import sys
import os
import io
import json
import hashlib
import subprocess
from pathlib import Path

# Forcer l'encodage UTF-8 pour Windows (évite les erreurs avec les emojis)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Imports scientifiques
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Imports ML
from sklearn.model_selection import train_test_split

# Imports du projet
from src.fdd.ml_models import FDDClassifier, FDDPipeline
from src.fdd.visualization import FDDVisualizer
from src.physics.simulator import HAS_COOLPROP
from src.studies.synthetic.generator import FaultDataGenerator, FaultType
from src.studies.synthetic.paths import MODELS, OUTPUTS, STUDY


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_stamp() -> dict:
    root = Path(__file__).resolve().parent
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return {"git_sha": sha, "git_dirty": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return {"git_sha": None, "git_dirty": None}


def print_header(title: str):
    """Affiche un en-tête formaté."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    """Fonction principale d'analyse FDD."""
    
    print_header("🔬 DIAGNOSTIC DE PANNES PAR MACHINE LEARNING (FDD)")
    print("\nAnalyse des défauts sur Pompes à Chaleur")
    print("Basé sur la thermodynamique du cycle à compression de vapeur")
    
    # Configuration
    N_SAMPLES = 5000
    RANDOM_SEED = 42
    OUTPUT_DIR = str(OUTPUTS)
    MODEL_DIR = str(MODELS)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # =========================================================================
    # 1. GÉNÉRATION DU DATASET
    # =========================================================================
    print_header("1. GÉNÉRATION DU DATASET")
    
    # Distribution des classes
    fault_distribution = {
        FaultType.NORMAL: 0.40,
        FaultType.CONDENSER_FOULING: 0.15,
        FaultType.EVAPORATOR_FOULING: 0.15,
        FaultType.REFRIGERANT_UNDERCHARGE: 0.10,
        FaultType.CONDENSER_FAN_FAULT: 0.10,
        FaultType.EVAPORATOR_FAN_FAULT: 0.10,
    }
    
    print(f"\n📊 Configuration:")
    print(f"   - Nombre d'échantillons: {N_SAMPLES}")
    print(f"   - Seed aléatoire: {RANDOM_SEED}")
    print(f"   - Classes: {len(fault_distribution)}")
    
    # Générer les données
    generator = FaultDataGenerator(random_seed=RANDOM_SEED)
    
    print(f"\n🔄 Génération en cours...")
    df = generator.generate_dataset(
        n_samples=N_SAMPLES,
        fault_distribution=fault_distribution,
        show_progress=True
    )
    
    print(f"\n✅ Dataset généré: {len(df)} échantillons")
    if generator.n_rejected or generator.n_dropped_nan:
        print(
            f"   ⚠️  Rejets simulateur: {generator.n_rejected}  "
            f"lignes non finies: {generator.n_dropped_nan}"
        )
    
    # Distribution des classes
    print(f"\n📈 Distribution des défauts:")
    print("-" * 50)
    class_counts = df['fault_type'].value_counts()
    for fault, count in class_counts.items():
        pct = count / len(df) * 100
        bar = "█" * int(pct / 2)
        print(f"   {fault:30} | {count:5} ({pct:5.1f}%) {bar}")
    
    # Sauvegarder le dataset
    df.to_csv(f'{OUTPUT_DIR}/dataset.csv', index=False, sep=',')
    print(f"\n💾 Dataset sauvegardé: {OUTPUT_DIR}/dataset.csv")
    
    # =========================================================================
    # 2. PRÉPARATION DES DONNÉES
    # =========================================================================
    print_header("2. PRÉPARATION DES DONNÉES")
    
    feature_cols = generator.get_feature_columns()
    label_col = generator.get_label_column()
    
    X = df[feature_cols]
    y = df[label_col]
    
    # Split train / val / test. Selection never sees the test split.
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y,
        test_size=0.3,
        random_state=RANDOM_SEED,
        stratify=y,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval,
        test_size=0.25,
        random_state=RANDOM_SEED,
        stratify=y_trainval,
    )

    print(f"\n📊 Données préparées:")
    print(f"   - Train: {len(X_train)} échantillons")
    print(f"   - Val:   {len(X_val)} échantillons  (sélection)")
    print(f"   - Test:  {len(X_test)} échantillons  (jamais pour choisir)")
    print(f"   - Features: {len(feature_cols)}")
    print(f"   - Classes: {y.nunique()}")
    
    # Statistiques
    print(f"\n📊 Statistiques des features clés:")
    print(df[['P_evap', 'P_cond', 'T_discharge', 'COP']].describe().round(2))
    
    # =========================================================================
    # 3. ENTRAÎNEMENT DES MODÈLES
    # =========================================================================
    print_header("3. ENTRAÎNEMENT DES MODÈLES ML")
    
    # Pipeline multi-modèles
    pipeline = FDDPipeline(random_state=RANDOM_SEED)
    pipeline.add_all_models()
    
    print(f"\n🤖 Modèles à entraîner: {list(pipeline.models.keys())}")
    print("\n🚀 Entraînement en cours...")
    
    # Entraîner et évaluer
    results = pipeline.fit_evaluate_all(
        X_train, y_train,
        X_val, y_val,
        X_test, y_test,
        feature_cols,
    )
    
    # Tableau comparatif
    comparison_df = pipeline.get_comparison_table()
    print(f"\n📊 Tableau Comparatif des Modèles:")
    print("-" * 70)
    print(comparison_df.to_string(index=False))
    
    # Sauvegarder
    comparison_df.to_csv(f'{OUTPUT_DIR}/model_comparison.csv', index=False, sep=',')
    
    # =========================================================================
    # 4. ANALYSE DU MEILLEUR MODÈLE
    # =========================================================================
    print_header("4. ANALYSE DU MEILLEUR MODÈLE")
    
    best_model_name = pipeline.best_model_name or comparison_df.iloc[0]['Model']
    best_result = results[best_model_name]

    print(f"\n🏆 Modèle retenu (sélection sur val): {best_model_name}")
    print(f"\n   Accuracy test:  {best_result.accuracy:.4f}  "
          f"[{best_result.accuracy_ci_low:.3f}, {best_result.accuracy_ci_high:.3f}]")
    print(f"   Precision: {best_result.precision_macro:.4f}")
    print(f"   Recall:    {best_result.recall_macro:.4f}")
    print(f"   F1 Score:  {best_result.f1_macro:.4f}")
    
    # Rapport de classification
    print(f"\n📋 Rapport de Classification:")
    print("-" * 70)
    print(best_result.classification_report)
    
    # Importance des features
    if best_result.feature_importance is not None:
        print(f"\n🔑 Top 10 Variables Importantes:")
        print("-" * 50)
        for i, row in best_result.feature_importance.head(10).iterrows():
            bar = "█" * int(row['importance'] * 50)
            print(f"   {row['feature']:25} | {row['importance']:.4f} {bar}")
        
        # Sauvegarder
        best_result.feature_importance.to_csv(
            f'{OUTPUT_DIR}/feature_importance.csv', index=False, sep=','
        )
    
    best_classifier = pipeline.models[best_model_name]
    labels = list(best_classifier.class_names)
    cm_df = pd.DataFrame(
        best_result.confusion_matrix,
        index=labels,
        columns=labels,
    )
    cm_norm = cm_df.div(cm_df.sum(axis=1).replace(0, 1), axis=0)
    cm_norm.to_csv(f'{OUTPUT_DIR}/confusion_matrix.csv')
    pd.DataFrame({
        'y_true': y_test.values,
        'y_pred': best_result.predictions,
    }).to_csv(f'{OUTPUT_DIR}/test_predictions.csv', index=False)

    model_path = os.path.join(MODEL_DIR, 'classifier.joblib')
    best_classifier.save(model_path)
    from sklearn import __version__ as sklearn_version
    from sklearn.metrics import classification_report as _cls_report

    per_class = _cls_report(
        y_test, best_result.predictions, labels=labels, output_dict=True, zero_division=0
    )
    metadata = {
        'model_name': best_model_name,
        'model_type': best_classifier.model_type,
        'accuracy': float(best_result.accuracy),
        'accuracy_ci_low': float(best_result.accuracy_ci_low),
        'accuracy_ci_high': float(best_result.accuracy_ci_high),
        'precision': float(best_result.precision_macro),
        'recall': float(best_result.recall_macro),
        'f1': float(best_result.f1_macro),
        'f1_per_class': {
            name: float(per_class[name]['f1-score'])
            for name in labels
            if name in per_class
        },
        'n_samples': int(len(df)),
        'n_train': int(len(X_train)),
        'n_val': int(len(X_val)),
        'n_test': int(len(X_test)),
        'n_features': int(len(feature_cols)),
        'features': feature_cols,
        'classes': labels,
        'coolprop': bool(HAS_COOLPROP),
        'calibrated': best_classifier.model_type == 'gradient_boosting',
        'selected_on': 'val',
        'random_state': RANDOM_SEED,
        'sklearn_version': sklearn_version,
        'dataset_sha256': _sha256(f'{OUTPUT_DIR}/dataset.csv'),
        'n_rejected': int(generator.n_rejected),
        'n_dropped_nan': int(generator.n_dropped_nan),
        'study': STUDY,
        'mode': 'heating',
        'source': 'simulator',
        'taxonomy': 'project-6class',
    }
    metadata.update(_git_stamp())
    with open(os.path.join(MODEL_DIR, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    print(f"\n💾 Modèle sauvegardé: {model_path}")

    # =========================================================================
    # 5. VALIDATION CROISÉE
    # =========================================================================
    print_header("5. VALIDATION CROISÉE")
    
    best_classifier = pipeline.models[best_model_name]
    cv_mean, cv_std = best_classifier.cross_validate(
        X_train, y_train,
        cv=5, feature_columns=feature_cols
    )

    print(f"\n🔄 Validation Croisée (5-fold, train seulement):")
    print(f"   F1 Score Moyen: {cv_mean:.4f}")
    print(f"   Écart-type:     {cv_std:.4f}")
    print(f"   Intervalle 95%: [{cv_mean - 1.96*cv_std:.4f}, {cv_mean + 1.96*cv_std:.4f}]")

    from tools.results import log
    model_slug = best_classifier.model_type.replace("_", "-")
    ci_note = (
        f"95% Wilson CI [{best_result.accuracy_ci_low:.3f}, {best_result.accuracy_ci_high:.3f}]; "
        f"selected on val; CV-train F1={cv_mean:.3f}±{cv_std:.3f}"
    )
    log(
        experiment="X0", protocol="holdout-test", reference="simulated",
        features="24-col", model=model_slug, label="__global__",
        metric="accuracy", value=float(best_result.accuracy),
        n=int(best_result.n), note=ci_note,
    )
    log(
        experiment="X0", protocol="holdout-test", reference="simulated",
        features="24-col", model=model_slug, label="__global__",
        metric="f1", value=float(best_result.f1_macro),
        n=int(best_result.n), note="macro; selected on val",
    )
    log(
        experiment="X0", protocol="cv-train", reference="simulated",
        features="24-col", model=model_slug, label="__global__",
        metric="f1", value=float(cv_mean),
        n=int(len(X_train)), note=f"5-fold stratified, train only, std={cv_std:.4f}",
    )
    
    # =========================================================================
    # 6. VISUALISATIONS
    # =========================================================================
    print_header("6. GÉNÉRATION DES VISUALISATIONS")
    
    viz = FDDVisualizer(figsize=(12, 8), dpi=100)
    
    # Matrice de confusion
    print("\n📊 Génération de la matrice de confusion...")
    fig = viz.plot_confusion_matrix(
        best_result.confusion_matrix,
        labels,
        title=f"Matrice de Confusion - {best_model_name}",
        normalize=True,
        save_path=f'{OUTPUT_DIR}/confusion_matrix.png'
    )
    plt.close()
    
    # Comparaison des modèles
    print("📊 Génération de la comparaison des modèles...")
    fig = viz.plot_model_comparison(
        comparison_df,
        title="Comparaison des Algorithmes ML",
        save_path=f'{OUTPUT_DIR}/model_comparison.png'
    )
    plt.close()
    
    # Importance des features
    if best_result.feature_importance is not None:
        print("📊 Génération de l'importance des features...")
        fig = viz.plot_feature_importance(
            best_result.feature_importance,
            top_n=15,
            title=f"Importance des Variables - {best_model_name}",
            save_path=f'{OUTPUT_DIR}/feature_importance.png'
        )
        plt.close()
    
    # Distribution des données
    print("📊 Génération de la distribution des données...")
    key_features = ['P_evap', 'P_cond', 'T_discharge', 'COP', 'superheat', 'compression_ratio']
    fig = viz.plot_data_distribution(
        df, key_features, 'fault_type',
        title="Distribution des Variables par Type de Défaut",
        save_path=f'{OUTPUT_DIR}/data_distribution.png'
    )
    plt.close()
    
    # Enveloppe compresseur
    print("📊 Génération de l'enveloppe de fonctionnement...")
    sampled = df.sample(100, random_state=RANDOM_SEED)
    operating_points = list(zip(sampled['T_evap'], sampled['T_cond']))
    fig = viz.plot_compressor_envelope(
        operating_points=operating_points,
        save_path=f'{OUTPUT_DIR}/compressor_envelope.png'
    )
    plt.close()
    
    # Figure de synthèse
    print("📊 Génération de la figure de synthèse...")
    fig = viz.create_report_figure(
        results, df, feature_cols, 'fault_type',
        save_path=f'{OUTPUT_DIR}/fdd_overview.png',
        best_name=best_model_name,
    )
    plt.close()
    
    print(f"\n✅ Toutes les visualisations sauvegardées dans {OUTPUT_DIR}/")
    
    # =========================================================================
    # 7. DÉMONSTRATION DE PRÉDICTION
    # =========================================================================
    print_header("7. DÉMONSTRATION DE DIAGNOSTIC")
    
    from src.fdd.inference import FDDEngine
    from src.studies.synthetic.scenarios import SyntheticScenarios

    engine = FDDEngine(model_path)
    scenarios = SyntheticScenarios(engine)

    test_cases = [
        {"name": "Conditions normales", "T_source": 7, "T_sink": 40,
         "speed": 0.7, "fault_type": "Normal"},
        {"name": "Condenseur encrassé 30%", "T_source": 7, "T_sink": 40,
         "speed": 0.7, "fault_type": "Condenser_Fouling"},
        {"name": "Évaporateur encrassé 25%", "T_source": 7, "T_sink": 40,
         "speed": 0.7, "fault_type": "Evaporator_Fouling"},
        {"name": "Fuite réfrigérant 20%", "T_source": 7, "T_sink": 40,
         "speed": 0.7, "fault_type": "Refrigerant_Undercharge"},
    ]

    print("\n🎯 Test de diagnostic sur cas simulés:\n")

    for case in test_cases:
        payload = scenarios.simulate_cycle(
            T_source=case["T_source"],
            T_sink=case["T_sink"],
            speed_ratio=case["speed"],
            fault_type=case["fault_type"],
        )
        print(f"   📌 {case['name']}:")
        print(f"      COP simulé: {payload['cycle']['COP']:.2f}")
        print(f"      ➡️  Diagnostic IA: {payload['diagnosis']['label']}")
        print(f"      Confiance: {payload['diagnosis']['confidence']*100:.1f}%\n")
    
    # =========================================================================
    # RÉSUMÉ FINAL
    # =========================================================================
    print_header("RÉSUMÉ DU PROJET FDD")
    
    print(f"""
    📊 Dataset: {len(df)} échantillons, {len(feature_cols)} features
    🤖 Meilleur Modèle: {best_model_name}
    🎯 F1 Score: {best_result.f1_macro:.4f}
    ✅ Accuracy: {best_result.accuracy:.4f}
    
    🔑 Top 3 Variables Importantes:""")
    
    if best_result.feature_importance is not None:
        for i, row in best_result.feature_importance.head(3).iterrows():
            print(f"       {i+1}. {row['feature']}: {row['importance']:.4f}")
    
    print(f"""
    📁 Fichiers générés dans {OUTPUT_DIR}/:
       - dataset.csv
       - model_comparison.csv
       - feature_importance.csv
       - confusion_matrix.csv
       - test_predictions.csv
       - models/synthetic/classifier.joblib
    """)
    
    print("=" * 70)
    print("  🎉 ANALYSE TERMINÉE AVEC SUCCÈS!")
    print("=" * 70)
    
    return results, comparison_df, best_result


if __name__ == "__main__":
    results, comparison_df, best_result = main()



