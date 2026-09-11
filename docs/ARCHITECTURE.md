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

## Training data

The training set is **entirely synthetic**. No measured data feeds the model.

`main_analysis.py` runs `FaultDataGenerator.generate_dataset()`, which samples operating
points uniformly from `T_source ∈ (-10, 20) °C`, `T_sink ∈ (30, 55) °C`,
`speed_ratio ∈ (0.3, 1.0)`, injects a fault by degrading physical parameters in
`simulator.py` (heat-exchanger `UA`, airflow ratio, refrigerant charge), then adds Gaussian
measurement noise. The result is written to `outputs/dataset_fdd.csv` — 5000 rows,
2000 `Normal` and 3000 faulted across 5 fault classes — and that CSV is what both the
trainer and the dashboard routes read.

`data/nistir_7350_data_in_appendix_d(NF).csv` is **not read by any code**. It is the
fault-free baseline table from NISTIR 7350, kept as a physical reference.

`FaultType` declares 8 faults, but the default distribution generates 6. Both
`REFRIGERANT_OVERCHARGE` and `COMPRESSOR_VALVE_LEAK` have a complete `FaultConfig` and
injection branch that no shipped dataset exercises.

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

Validation against measured data has not been done. The relevant experiments are public
and free — NIST publications are US government work.

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

## Target structure

The repository currently assumes a single study: the simulator is the only data source, and
that assumption is wired into the shared layers. Supporting a second study — measured NIST
data — means separating three concerns that are presently mixed.

```
src/
├── physics/          the physical model
│   ├── simulator.py
│   ├── thermo_lab.py
│   └── thermodynamic_viz.py
│
├── fdd/              the method, shared by every study
│   ├── features.py       feature contract + Li & Braun residuals
│   ├── ml_models.py      trainer
│   └── inference.py      FDDEngine: load a model, diagnose a vector
│
└── studies/
    ├── synthetic/    heating, A7/W40, own taxonomy
    │   ├── generator.py
    │   └── taxonomy.py
    └── nist/         cooling, air-to-air, NIST taxonomy
        ├── loader.py
        └── taxonomy.py

outputs/<study>/      models/<study>/
```

Layering rule: `studies/` may import `fdd/` and `physics/`; `fdd/` may import `physics/`;
`physics/` imports nothing from the project. Two current edges violate it.

### Coupling 1 — `FDDEngine` contains the synthetic study

`src/inference.py` instantiates `FaultDataGenerator` (line 51), owns `FAULT_PARAM_MAP`
(line 21) mapping class names to simulator parameters, and exposes `simulate_cycle()`
(line 84). Those are synthetic-study concerns living inside the shared engine.

Split it by responsibility:

- **diagnose** — load model and metadata, score a feature vector → stays in `fdd/inference.py`
- **simulate** — build a faulted cycle for the demo → moves to `studies/synthetic/`

This is the same seam as the API split: `/predict` and `/health` are diagnosis, `/simulate`
and `/live` are the synthetic study driving the demo.

### Coupling 2 — the default baseline is simulated

`features.py::cycle_to_features` falls back to `healthy_cycle()`, which calls the simulator.
The `baseline=` parameter already allows an external reference to be injected, so no
signature changes; what is needed is that the default be understood as the synthetic
study's choice rather than a property of the method.

### What is already safe

`models/fdd_classifier.joblib` contains **no reference to any project module** — only
scikit-learn classes (`sklearn.ensemble._gb`, `sklearn.calibration`, …). `joblib.dump` saved
the estimator, not the `FDDClassifier` wrapper. Moving `ml_models.py` will not break model
loading. `api/` does not move, so the Dockerfile `CMD` is unaffected.

### What breaks silently

`dashboard.py` and `scripts/generate_ml_graphs.py` import from `src` and **no test covers
them**. They must be updated with everything else or they fail only when someone runs them.

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
