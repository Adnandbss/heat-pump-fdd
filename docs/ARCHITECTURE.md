# Architecture

How a reading goes from the simulated cycle to a fault label on the dashboard, and which
modules are on that path.

```
simulator.py  →  features.py  →  data_generator.py  →  ml_models.py  →  inference.py  →  api/app.py  →  web/
  R410A cycle     24 features      labelled samples     GradientBoosting   FDDEngine       FastAPI       React
```

## Modules on the serving path

| Module | Exports | Pulled in by |
|---|---|---|
| `src/simulator.py` | `HeatPumpSimulator`, `CycleResults`, `RefrigerantProperties`, `HAS_COOLPROP` | `features`, `data_generator`, `inference` |
| `src/features.py` | `FEATURE_COLUMNS` (24), `SCENARIOS`, `cycle_to_features` | `data_generator`, `inference`, `api/app` |
| `src/data_generator.py` | `FaultDataGenerator`, `FaultType` | `inference` |
| `src/ml_models.py` | `FDDClassifier` | `inference` |
| `src/inference.py` | `FDDEngine`, `FAULT_PARAM_MAP` | `api/app` |
| `src/thermo_lab.py` | P-h / COP lab helpers | `api/app` |
| `src/thermodynamic_viz.py` | `ThermodynamicVisualizer`, `R410A`, `HAS_COOLPROP` | `api/app`, `thermo_lab` |
| `api/schemas.py` | Pydantic request/response contracts | `api/app` |

Feature and class lists are mirrored in `models/metadata.json`; treat that file as the
record of what the shipped model was trained on.

## Not on the serving path

`dashboard.py` (Streamlit), `src/service.py` (httpx client used by Streamlit),
`src/visualization.py`, `main_analysis.py` (training entry point), `scripts/`.

Removing any of these would not affect `api/app.py` or the React app.

## API surface

`api/app.py` serves two distinct concerns from one module:

- **Inference** — `POST /predict`, `POST /simulate`, `POST /live`, `GET /health`
- **Dashboard** — 17 `GET /api/*` routes (stats, overview, catalog, dataset, explore,
  thermo, advanced) that exist to feed the React views

A split along that seam is the natural next refactor.

## Tests

`pytest.ini` sets `pythonpath = .`, so run `pytest` from the repo root.

| File | Covers |
|---|---|
| `tests/test_thermo.py` | R410A saturation pressure, nominal cycle invariants (COP, `P_cond > P_evap`) |
| `tests/test_features.py` | 24-column contract, feature keys, fault signatures stay distinguishable |
| `tests/test_api.py` | `FDDEngine` diagnoses, route contracts, schema rejection (skipped without `models/`) |

## Gotcha: the committed model is a pickle

`models/fdd_classifier.joblib` is a pickled scikit-learn `GradientBoosting` estimator
tracked in git, so **the `scikit-learn==1.6.1` pin in `requirements.txt` is load-bearing**.

Installing a different minor version makes the model fail to unpickle, and every test that
touches `FDDEngine` fails with an error that looks nothing like a version problem:

```
ModuleNotFoundError: No module named '_loss'
```

The Docker image is safe (it installs from `requirements.txt`). A local virtualenv that has
drifted is not. Upgrading scikit-learn requires retraining and recommitting the model via
`main_analysis.py` — never the upgrade alone.
