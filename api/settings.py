"""Process configuration. Override with `FDD_*` environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Study to serve, artefact paths, and CORS. Defaults match the shipped demo."""

    model_config = SettingsConfigDict(env_prefix="FDD_", extra="ignore")

    study: str = "synthetic"
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    classifier_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    dataset_path: Optional[Path] = None
    comparison_path: Optional[Path] = None
    confusion_path: Optional[Path] = None
    importance_path: Optional[Path] = None
    results_path: Optional[Path] = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [part.strip() for part in raw.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _default_study_paths(self) -> "Settings":
        models = ROOT / "models" / self.study
        outputs = ROOT / "outputs" / self.study
        self.classifier_path = self.classifier_path or models / "classifier.joblib"
        self.metadata_path = self.metadata_path or models / "metadata.json"
        self.dataset_path = self.dataset_path or outputs / "dataset.csv"
        self.comparison_path = self.comparison_path or outputs / "model_comparison.csv"
        self.confusion_path = self.confusion_path or outputs / "confusion_matrix.csv"
        self.importance_path = self.importance_path or outputs / "feature_importance.csv"
        self.results_path = self.results_path or ROOT / "outputs" / "results.csv"
        return self
