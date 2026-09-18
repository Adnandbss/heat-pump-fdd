# Architecture

How a reading goes from the simulated cycle to a fault label on the dashboard, and which
modules are on that path.

```
physics/simulator.py → fdd/features.py → studies/synthetic/generator.py → fdd/ml_models.py → fdd/inference.py → api/app.py → web/
     R410A cycle         24 features          labelled samples              sklearn.Pipeline     FDDEngine        FastAPI      React
```

## Layers

`src/` is organised in three layers. The import rule is one-directional:

```
studies/  →  fdd/  →  physics/
```

`physics/` imports nothing from the project; `fdd/` may import `physics/`; only `studies/`
may import both. Five tests enforce it (`test_engine_has_no_synthetic_study_api`,
`test_features_module_has_no_study_taxonomy`, `test_ml_models_does_not_import_the_data_generator`,
and the package guards in `test_packages.py`).

| Module | Exports | Pulled in by |
|---|---|---|
| `src/physics/simulator.py` | `HeatPumpSimulator`, `CycleResults`, `RefrigerantProperties`, `HAS_COOLPROP` | `features`, `generator`, `scenarios` |
| `src/physics/thermo_lab.py` | P-h / COP lab helpers | `api/app.py` |
| `src/physics/thermodynamic_viz.py` | `ThermodynamicVisualizer`, `R410A`, `HAS_COOLPROP` | `api/app.py`, `thermo_lab` |
| `src/fdd/features.py` | `FEATURE_COLUMNS` (24), `cycle_to_features`, `healthy_cycle` | `generator`, `scenarios`, `api/app.py` |
| `src/fdd/ml_models.py` | `FDDClassifier`, `FDDPipeline` | `inference`, `main_analysis.py` |
| `src/fdd/inference.py` | `FDDEngine` — load a model, diagnose a vector | `api/app.py` |
| `src/studies/synthetic/generator.py` | `FaultDataGenerator`, `FaultType` | `scenarios` |
| `src/studies/synthetic/scenarios.py` | `SyntheticScenarios` — `simulate_cycle`, `live_trace` | `api/app.py` |
| `src/studies/synthetic/taxonomy.py` | `FAULT_PARAM_MAP`, `SCENARIOS` | `api/app.py` |
| `src/studies/synthetic/paths.py` | `STUDY`, `DATASET_PATH`, `CLASSIFIER_PATH`, … | `api/app.py`, `inference`, `scripts/` |
| `api/schemas.py` | Pydantic request/response contracts | `api/app.py` |

`FDDEngine` only diagnoses. Building a faulted cycle for the demo belongs to
`SyntheticScenarios`, which wraps an engine — the same seam as the API surface below.

Artefact locations come from `paths.py` alone; no path is hard-coded elsewhere. Feature and
class lists are mirrored in `models/synthetic/metadata.json`, which also records the study it
came from (`study`, `mode`, `source`, `taxonomy`).

## Not on the serving path

`dashboard.py` (Streamlit), `src/service.py` (httpx client used by Streamlit),
`src/fdd/visualization.py` (training-time plots), `main_analysis.py` (training entry point),
`scripts/`.

Removing any of these would not affect `api/app.py` or the React app. None of them is covered
by a test, so **`pytest` stays green even if they are broken** — check them by hand
(`python -c "import dashboard"`) after any move.

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
| `tests/test_thermo.py` | R410A saturation pressure, nominal cycle invariants |
| `tests/test_features.py` | 24-column contract, fault signatures stay distinguishable |
| `tests/test_scenarios.py` | `simulate_cycle`, `live_trace`, severity overrides |
| `tests/test_inference.py` | `FDDEngine` predicts, and carries no study API |
| `tests/test_taxonomy.py` | `FAULT_PARAM_MAP` / `SCENARIOS` stay aligned |
| `tests/test_paths.py` | artefact layout per study |
| `tests/test_packages.py`, `tests/test_ml_models.py` | layering guards |
| `tests/test_api.py` | route contracts, schema rejection (skipped without a model) |

76 tests today.

## Training data

The training set is **entirely synthetic**. No measured data feeds the model.

`main_analysis.py` runs `FaultDataGenerator.generate_dataset()`, which samples operating
points uniformly from `T_source ∈ (-10, 20) °C`, `T_sink ∈ (30, 55) °C`,
`speed_ratio ∈ (0.3, 1.0)`, injects a fault by degrading physical parameters in
`simulator.py` (heat-exchanger `UA`, airflow ratio, refrigerant charge), then adds Gaussian
measurement noise and **recomputes derived quantities** (`COP`, ratios, pinches, residuals)
from the noisy sensors. The result is written to `outputs/synthetic/dataset.csv` — 5000 rows,
2000 `Normal` and 3000 faulted (500 each of 6 fault classes) — and that CSV is what both the
trainer and the dashboard routes read.

`data/nistir_7350_data_in_appendix_d(NF).csv` is **not read by any code**. It is the
fault-free baseline table from NISTIR 7350, kept as a physical reference.

`FaultType` declares 7 classes, all of which the default mix generates. A test
(`tests/test_fault_taxonomy.py`) asserts `FaultType` == dataset labels ==
`metadata.json["classes"]`. `COMPRESSOR_VALVE_LEAK` was removed: the simulator has no
volumetric-efficiency parameter, and the old injection branch was a mix of undercharge and
evaporator fouling. Modelling a real valve leak is simulator debt, not a generator flag.

## Known limits

Because the same simulator produces both the training and the test split, and the split is
random over a densely sampled continuous domain, reported accuracy measures **how
separable the fault signatures are inside the physical model** — not detection performance
on hardware. There is no out-of-domain hold-out and no `GroupKFold` over operating
conditions. Quote the metric accordingly.

The 24 features are residuals against a healthy cycle (`d_COP`, `d_superheat`,
`d_subcooling`, `d_T_discharge`, `d_W_comp`). That is the design choice that makes transfer
to measured data plausible, since residuals cancel part of the unit- and sensor-specific
bias.

## External validation: published NIST datasets

Validation against measured data **has been done** (leave-one-machine-out on the NIST 14/16
SEER campaign). Method and numbers: [NIST_FINDINGS](NIST_FINDINGS.md). The relevant
experiments are public and free — NIST publications are US government work.

| Source | Mode | Faults imposed | Relevance |
|---|---|---|---|
| [NIST TN 1648](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1648_2009.pdf) (Payne, Yoon & Domanski, 2009) | **Heating** | 6: indoor/outdoor airflow, compressor & four-way valve leakage, liquid-line restriction, over- and undercharge | Closest match. Chapter 5 tabulates feature slopes and residuals vs fault level in SI units, at indoor 21.1 °C with outdoor −8.3 °C and 8.3 °C — inside this simulator's `T_source` range |
| [NISTIR 7350](https://www.nist.gov/publications/performance-residential-heat-pump-operating-cooling-mode-single-faults-imposed-nistir) (Kim, Payne, Domanski & Hermes, 2006) | Cooling | 7, adding non-condensable gas | Source of the `data/` baseline; faulted tables live in the same report |
| [NIST FDD Research Data](https://www.nist.gov/el/energy-and-environment-division-73200/hvacr-equipment-performance-group/fault-detection-and) | Cooling | 14 & 16 SEER test campaign | Direct `.xlsx` downloads, including the full 2019 dataset |
| [NIST TN 1848](https://nvlpubs.nist.gov/nistpubs/technicalnotes/nist.tn.1848.pdf) | — | Installation-fault sensitivity analysis | Context on fault severity ranges |

TN 1648 defines its residuals as *the fault-imposed value minus the fault-free value at the
same test condition* — the same quantity as the `d_*` features here, which makes the slopes
directly comparable to a `fan_cond_ratio` or `refrigerant_charge` sweep of the simulator.

Two traps when using it:

- **In heating mode NIST calls the indoor coil the condenser.** Their *Condenser Air Flow
  Fault* varies indoor airflow. Mapping it onto `fan_cond_ratio` without checking which
  coil this simulator treats as the condenser validates the wrong sign.
- Chapter 5 publishes fitted slopes and plots rather than per-test rows. Raw rows come from
  the cooling-mode spreadsheets or from NIST on request.

## Gotcha: the committed model is a pickle

`models/synthetic/classifier.joblib` is a pickled scikit-learn `Pipeline` (`StandardScaler`
+ Random Forest) tracked in git, so **the `scikit-learn==1.6.1` pin in `requirements.txt` is load-bearing**.

Installing a different minor version makes the model fail to unpickle, and every test that
touches `FDDEngine` fails with an error that looks nothing like a version problem:

```
ModuleNotFoundError: No module named '_loss'
```

The Docker image is safe (it installs from `requirements.txt`). A local virtualenv that has
drifted is not. Upgrading scikit-learn requires retraining and recommitting the model via
`main_analysis.py` — never the upgrade alone.
