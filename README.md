# Heat Pump Fault Detection & Diagnostics

[![CI](https://github.com/Adnandbss/heat-pump-fdd/actions/workflows/ci.yml/badge.svg)](https://github.com/Adnandbss/heat-pump-fdd/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.6.1-orange)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Licence](https://img.shields.io/badge/licence-MIT-lightgrey)

This repository is a **validation methodology** for heat-pump FDD, not a field detector.
The interesting result is how much a number moves when the protocol becomes honest.

![Evidence dashboard: every figure reads outputs/results.csv](docs/front/00-full.png)

Each figure on that page is read from `outputs/results.csv` and carries its validation protocol.

## 60-second demo

```bash
make dev
```

API at `http://localhost:8000/docs`, glass dashboard at `http://localhost:5173`.
Or the two terminals:

```bash
pip install -r requirements.txt
uvicorn api.app:app --reload          # http://localhost:8000/docs
cd web && npm install && npm run dev  # http://localhost:5173
```

The dashboard loads COP, class mix, a fouling injection trace, and the Evidence page
from `GET /api/*`. Recapture the figures after a front change:

```bash
make capture                          # or: cd web && npm run capture
```

Streamlit (`dashboard.py`) is still in the repo for P-h diagrams and manual inject controls:

```bash
streamlit run dashboard.py            # http://localhost:8501
```

Docker (API + React; Streamlit is not in the compose path):

```bash
docker compose up --build
```

Then open `http://localhost:5173`. The browser talks to `http://localhost:8000`.

## Why it exists

Fouling, fan faults and refrigerant leaks all hurt COP, but the signatures overlap. Threshold rules misfire. This project:

- Simulates physically consistent R410A cycles (CoolProp).
- Decouples condenser **fouling** (pinch / subcooling) from **fan** faults (airflow, compressor work, discharge temperature).
- Serves a classifier so Diagnosis / Live FDD show readable probabilities.

**For PM interviews:** the unit of value is a decision — fault class + confidence — not a notebook metric.
**For ML interviews:** the interesting part is the physics features and class overlap, not stacking more estimators.

## Architecture

```mermaid
flowchart LR
    sim[HeatPumpSimulator]
    feat[23 features]
    model[classifier.joblib]
    api[FastAPI]
    web[React Vite]

    sim --> feat --> model --> api --> web
```

| Path | Role |
|---|---|
| `src/physics/simulator.py` | Cycle model, CoolProp R410A, fault physics |
| `src/studies/synthetic/generator.py` | 5000 labelled operating points |
| `src/fdd/ml_models.py` | Random Forest (shipped) + tuned / calibrated Gradient Boosting |
| `src/fdd/inference.py` | Load the model and diagnose a feature vector |
| `src/service.py` | Streamlit client: API first, local fallback |
| `api/app.py` | `GET /health`, `POST /predict`, `POST /simulate`, `POST /live`, `GET /api/*` |
| `web/` | Glassmorphism dashboard (primary UI) |
| `dashboard.py` | Leftover Streamlit: exploration, live inject, P-h diagrams |
| `models/synthetic/` | Serialized classifier + metadata |

## Faults

| Class | Physical signature |
|---|---|
| Normal | Nominal A7/W40-like operation |
| Condenser_Fouling | Pinch up, subcooling up, modest discharge rise |
| Evaporator_Fouling | P_evap down, superheat up |
| Refrigerant_Undercharge | P_evap down, superheat up, capacity down |
| Condenser_Fan_Fault | Airflow down, P_cond and T_discharge rise, COP down |
| Evaporator_Fan_Fault | Airflow down, superheat and T_discharge down, capacity down |
| Refrigerant_Overcharge | P_cond and subcooling up, superheat down |

## Results

The protocol counts more than the model. The same residual features move from a leaked
0.996 on the simulator to leave-one-machine-out **0.602** on NIST, and to 0.318 when
the healthy reference is transferred.

<!-- results-source: X0/leaked-dCOP, X0/holdout-test, X0b/LOMO, X5/sim2real, X1/LOMO, X0b/majority-class -->

| Measured on | Protocol | Accuracy |
|---|---|---|
| Simulated | label leak (withdrawn) | 0.996 |
| Simulated | hold-out, 7 classes | **0.893** |
| NIST | LOMO, reference on the target machine | 0.602 |
| NIST | trained on the simulator (sim2real) | 0.454 |
| NIST | LOMO, transferred reference | 0.318 |
| — | majority class | 0.251 |

Hold-out on 5000 CoolProp cycles (23 features). Split: 2625 train / 875 val / 1500 test
(52.5 / 17.5 / 30 %). Scaler and classifier live in a `sklearn.Pipeline`. The model is
**selected on val**, never on test. Interval: 95 % Wilson on the 1500-row test set.

<!-- results-source: X0/holdout-test -->

| Model | Test accuracy | 95 % CI | Test F1 |
|---|---|---|---|
| **Random Forest (shipped)** | **89.3 %** | 87.7 – 90.8 | 0.871 |
| Gradient Boosting | 89.9 % | 88.2 – 91.3 | 0.879 |

The two models are tied on val (ΔF1 = 0.002). Random Forest is shipped: cheaper inference,
readable importances. 5-fold CV on **train only**: F1 0.886 ± 0.017.

Per-class F1 (test): `Condenser_Fan_Fault` 0.96, `Evaporator_Fan_Fault` 0.97, `Normal` 0.94,
`Refrigerant_Overcharge` 0.87, `Refrigerant_Undercharge` 0.83, `Evaporator_Fouling` 0.79,
`Condenser_Fouling` 0.74.

Adding overcharge (and dropping the unmodelled valve-leak ghost class) moved the headline
from 91.9 % [90.4 – 93.1] on six classes to **89.3 % [87.6 – 90.7]** on seven. Overcharge is
caught (F1 0.88); it is not collapsed into condenser fouling (11 / 150 overcharge test rows
called fouling, 9 / 150 the other way) once the generator stopped injecting fouling into
overcharge samples.

The previous 99.6 % was invalid: `d_COP` equalled the detection label (`== 0` on all 2000
fault-free rows, and on no other class). Derived quantities are now recomputed from the
noisy sensors; `d_COP` importance falls from 0.30 to 0.036. Logged in
`outputs/results.csv` (`X0` / `holdout-test`).

These numbers measure **how cleanly the simulator separates faults**, not field-labelled HVAC data. The demo still has to show that fouling is not predicted as a fan fault.

### Confronted with measured data

The residual design was checked against the NIST *FDD Heat Pump Cooling* campaign — 7375 chamber tests on two machines with imposed faults. Full method and figures in [docs/NIST_FINDINGS.md](docs/NIST_FINDINGS.md).

<!-- results-source: X0b/random-cv, X0b/LOMO -->

| Feature set | Random CV accuracy | Leave-one-machine-out accuracy |
|---|---|---|
| Raw measurements | 0.954 | 0.333 |
| Residuals only | 0.937 | **0.602** |

Every residual row above uses a healthy reference calibrated on the **target** machine. Rebuilt from the training machine only — a genuinely unknown unit — residuals-only drops to **0.318** (F1 macro 0.290), against 0.251 for the majority class. A second-order polynomial with indoor dew point, the form NIST itself uses, reaches 0.302; a random forest 0.265. No reference model tried lifts that ceiling.

Two things follow. **Residuals nearly double detection when the healthy reference is calibrated on the target machine** (0.333 → 0.602). And **a random split scores 0.95 where an honest one scores 0.60** — so any accuracy figure here, including the 89.3 % above, has to name its validation protocol.

### What calibration costs

If residual FDD needs healthy data from the machine in service, the practical question is how much. Measured by leave-one-machine-out over 20 draws, with the calibrating tests held out of the test set:

<!-- results-source: X1/LOMO-calibration-n10, X1/LOMO-calibration-n50, X0b/LOMO, X1/LOMO -->

| Healthy tests from the target machine | Accuracy | F1 macro |
|---|---|---|
| 0 — transferred reference | 0.318 | 0.290 |
| 10 | 0.377 | 0.324 |
| 50 | 0.456 | 0.380 |
| all (~625–727) | 0.602 | 0.479 |

**Fifty healthy tests recover only about 49% of the gap.** Reaching 90% takes essentially the full set. Spreading the sampled tests across the operating range rather than drawing at random helps most when few are available.

The field reading: a handful of commissioning measurements is not a calibration. Covering the operating envelope is what matters, and that is a deployment constraint rather than an algorithmic one.

Replay: `python EDA/x1_calibration_compute.py`. The Evidence page plots the same rows.

`docs/FRONT_EVIDENCE.pdf` and the NIST PNGs under `docs/` are generated artefacts
(`web/scripts/capture_evidence.mjs` and the EDA compute scripts). They are kept in
git so the dossier builds offline; they are not a second source of numbers.

## Known limits

Condenser fouling does not transfer (sim2real F1 0.000). Liquid-line restriction is
essentially never detected (LOMO F1 0.040). The model does not extrapolate across
severity (4-class accuracy 0.428 when trained on severe faults and tested on emerging
ones). Those three numbers are in `outputs/results.csv` (`X5` / `sim2real`, `X1` / `LOMO`,
`X4` / `holdout-severity-4class-<0.20`).

## Tests

```bash
make test
```

CI runs the same suite on every push, then the web lint / build / Playwright Evidence pass.
CoolProp saturation pressure at 0 °C must stay within 0.5% of 8.0 bar.

## License

MIT
