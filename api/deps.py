"""Request-scoped accessors. Nothing here runs at import time."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional

import pandas as pd
from fastapi import Depends, Request

from api.errors import ArtifactMissing
from api.settings import Settings
from src.fdd.inference import FDDEngine
from src.studies.synthetic.scenarios import SyntheticScenarios


class MtimeCache:
    """Keep a loaded value until the source file's mtime changes."""

    def __init__(self) -> None:
        self._mtime: Optional[float] = None
        self._value = None
        self._loaded = False

    def get(self, path: Optional[Path], loader: Callable):
        current = path.stat().st_mtime if path is not None and path.exists() else None
        if not self._loaded or current != self._mtime:
            self._value = loader()
            self._mtime = current
            self._loaded = True
        return self._value


def _caches(request: Request) -> Dict[str, MtimeCache]:
    caches = getattr(request.app.state, "caches", None)
    if caches is None:
        caches = {
            "dataset": MtimeCache(),
            "class_counts": MtimeCache(),
            "saturation": MtimeCache(),
        }
        request.app.state.caches = caches
    return caches


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _load_engine(request: Request) -> FDDEngine:
    engine = getattr(request.app.state, "engine", None)
    if engine is not None:
        return engine
    settings: Settings = request.app.state.settings
    try:
        engine = FDDEngine(settings.classifier_path, settings.metadata_path)
    except FileNotFoundError as exc:
        raise ArtifactMissing("classifier.joblib") from exc
    request.app.state.engine = engine
    request.app.state.scenarios = SyntheticScenarios(engine)
    return engine


def get_engine(request: Request) -> FDDEngine:
    return _load_engine(request)


def get_scenarios(request: Request) -> SyntheticScenarios:
    _load_engine(request)
    scenarios = getattr(request.app.state, "scenarios", None)
    if scenarios is None:
        raise ArtifactMissing("classifier.joblib")
    return scenarios


def read_artefact_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise ArtifactMissing(path.name)
    return pd.read_csv(path, **kwargs)


def get_dataset(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> pd.DataFrame:
    path = settings.dataset_path
    if not path.exists():
        raise ArtifactMissing(path.name)
    return _caches(request)["dataset"].get(path, lambda: pd.read_csv(path))


def get_class_counts(
    request: Request,
    engine: FDDEngine = Depends(get_engine),
    settings: Settings = Depends(get_settings),
) -> Dict[str, int]:
    path = settings.dataset_path

    def load() -> Dict[str, int]:
        if not path.exists():
            return {name: 0 for name in engine.class_names}
        counts = pd.read_csv(path)["fault_type"].value_counts().to_dict()
        return {name: int(counts.get(name, 0)) for name in engine.class_names}

    return _caches(request)["class_counts"].get(path, load)


def get_saturation_curve(request: Request):
    def load():
        import numpy as np

        from api.schemas.dashboard import SaturationPoint
        from src.physics.thermodynamic_viz import ThermodynamicVisualizer

        viz = ThermodynamicVisualizer()
        temps = np.linspace(-40, 70, 80)
        return tuple(
            SaturationPoint(
                T=float(T),
                P=float(viz._sat_pressure(float(T))),
                h_liq=float(viz._enthalpy_liquid(float(T))),
                h_vap=float(viz._enthalpy_vapor(float(T))),
            )
            for T in temps
        )

    return _caches(request)["saturation"].get(None, load)
