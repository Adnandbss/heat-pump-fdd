"""Regenerate the exploratory ML figures used in the FDD analysis."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.model_selection import learning_curve
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.fdd.ml_models import FDDClassifier
from src.studies.synthetic.paths import DATASET_PATH, OUTPUTS

OUTPUT_DIR = OUTPUTS / "ml_graphs"


def _read_dataset() -> pd.DataFrame:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        header = f.readline()
    sep = ";" if header.count(";") > header.count(",") else ","
    return pd.read_csv(DATASET_PATH, sep=sep)


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = _read_dataset()
    feature_cols = [
        c
        for c in df.columns
        if c not in {"fault_type", "fault_severity", "is_faulty"}
        and np.issubdtype(df[c].dtype, np.number)
    ]
    y = df["fault_type"]
    X = df[feature_cols]

    sns.set_theme(style="whitegrid")

    # Class distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    counts = y.value_counts()
    counts.plot(kind="bar", ax=axes[0], color=sns.color_palette("Set2", len(counts)))
    axes[0].set_title("Class distribution")
    axes[0].tick_params(axis="x", rotation=35)
    axes[1].pie(counts, labels=counts.index, autopct="%1.1f%%")
    axes[1].set_title("Fault mix")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "class_distribution.png", dpi=120)
    plt.close(fig)

    # Correlation
    fig, ax = plt.subplots(figsize=(12, 10))
    corr = X.corr(numeric_only=True)
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, cmap="RdBu_r", center=0, ax=ax, square=True)
    ax.set_title("Feature correlation")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "correlation_matrix.png", dpi=120)
    plt.close(fig)

    key = [c for c in ["P_evap", "P_cond", "superheat", "subcooling", "COP", "compression_ratio"] if c in X.columns]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, col in zip(axes.ravel(), key):
        for label, group in df.groupby("fault_type"):
            ax.hist(group[col], bins=30, alpha=0.45, label=label)
        ax.set_title(col)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle("Feature distributions by class")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "feature_distributions_by_class.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, col in zip(axes.ravel(), key):
        sns.boxplot(data=df, x="fault_type", y=col, ax=ax)
        ax.tick_params(axis="x", rotation=40, labelsize=7)
        ax.set_xlabel("")
    fig.suptitle("Boxplots by fault type")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "boxplots_by_fault.png", dpi=120)
    plt.close(fig)

    sample = df[key + ["fault_type"]].sample(min(500, len(df)), random_state=42)
    g = sns.pairplot(sample, hue="fault_type", diag_kind="kde", plot_kws={"alpha": 0.5, "s": 18})
    g.fig.savefig(OUTPUT_DIR / "pairplot_features.png", dpi=110)
    plt.close(g.fig)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    pca = PCA(n_components=3, random_state=42)
    Z = pca.fit_transform(Xs)
    fig, ax = plt.subplots(figsize=(8, 6))
    for label in y.unique():
        mask = y == label
        ax.scatter(Z[mask, 0], Z[mask, 1], s=12, alpha=0.6, label=label)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title("PCA (2D)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pca_visualization.png", dpi=120)
    plt.close(fig)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")
    for label in y.unique():
        mask = y == label
        ax.scatter(Z[mask, 0], Z[mask, 1], Z[mask, 2], s=8, alpha=0.5, label=label)
    ax.set_title("PCA (3D)")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pca_3d_visualization.png", dpi=120)
    plt.close(fig)

    idx = np.random.default_rng(42).choice(len(Xs), size=min(1000, len(Xs)), replace=False)
    tsne = TSNE(n_components=2, perplexity=30, random_state=42, init="pca")
    E = tsne.fit_transform(Xs[idx])
    fig, ax = plt.subplots(figsize=(8, 6))
    y_s = y.iloc[idx]
    for label in y_s.unique():
        mask = y_s == label
        ax.scatter(E[mask, 0], E[mask, 1], s=12, alpha=0.6, label=label)
    ax.set_title("t-SNE")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "tsne_visualization.png", dpi=120)
    plt.close(fig)

    clf = FDDClassifier(model_type="gradient_boosting")
    train_sizes, train_scores, val_scores = learning_curve(
        clf.model,
        X,
        y,
        cv=3,
        train_sizes=np.linspace(0.35, 1.0, 5),
        scoring="accuracy",
        n_jobs=-1,
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(train_sizes, train_scores.mean(axis=1), label="Train")
    ax.plot(train_sizes, val_scores.mean(axis=1), label="Validation")
    ax.fill_between(
        train_sizes,
        val_scores.mean(axis=1) - val_scores.std(axis=1),
        val_scores.mean(axis=1) + val_scores.std(axis=1),
        alpha=0.15,
    )
    ax.set_title("Learning curve (Gradient Boosting)")
    ax.set_xlabel("Training samples")
    ax.set_ylabel("Accuracy")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "learning_curves.png", dpi=120)
    plt.close(fig)

    print(f"Saved figures to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
