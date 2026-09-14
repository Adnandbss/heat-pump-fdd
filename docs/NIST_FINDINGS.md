# NIST dataset — exploration findings

Results of confronting this project's simulated fault signatures with the NIST *FDD Heat Pump
Cooling 14 & 16 SEER* campaign (7375 chamber tests, two machines, imposed faults).

Column mapping and unit conversions: [NIST_MAPPING.md](NIST_MAPPING.md).
Exploration notebooks are kept out of the repository; every number below is reproducible from
the dataset and the procedure described here.

## Dataset

| | |
|---|---|
| Tests | 7375 rows × 98 columns |
| Single-fault + fault-free | 5386 usable rows |
| Classes | 6 — no-fault, undercharge, overcharge, indoor airflow, liquid line, condenser blockage |
| Balance | 2.7:1 between largest and smallest class |
| Covariates | two machines (14 / 16 SEER), two lineset lengths |

Fault labels are implicit: they live in five level columns (`NF`, `EF`, `CF`, `LL`, `UC/OC`)
where 100 % means nominal. A fault counts as active when its level departs from nominal by
more than 2 %. That threshold reproduces the class counts exactly, so it can be asserted.

**Never put those five columns in a feature matrix** — they are the target.

## Trap: the suction pressure column is wrong on one machine

`1710_ODSuctPort_psia` reads as "compressor suction port pressure". On the **16 SEER unit it
is identical to discharge pressure in 100 % of rows** — the sensor was not instrumented and
the column carries the high-side value. That is 4085 rows, 55 % of the campaign.

Used unchecked it corrupts `P_evap`, `compression_ratio` and `pressure_ratio` with no error
raised: the pressure ratio collapses to exactly 1.00, which is physically impossible.

Use `1701_ODVapSV_psia` (vapour service valve) instead — ratio median 2.46, minimum 1.64,
consistent across both machines.

## Operating-domain overlap is 5.3 %

In cooling mode the indoor coil is the evaporator and the outdoor coil the condenser. Mapped
onto this project's heating-mode simulator:

| | NIST range | Simulator training range | Inside |
|---|---|---|---|
| `T_source` | 13.8 – 37.2 °C | −10 – 20 °C | 11.9 % |
| `T_sink` | 18.8 – 47.7 °C | 30 – 55 °C | 61.4 % |
| **both** | | | **392 / 7375 — 5.3 %** |

**Absolute-value comparison against the simulator is not available.** Comparing slopes and
signs of residuals against fault level remains valid, and is insensitive to the offset.

## Sign agreement: 12 / 16 (75 %)

Each quantity regressed on fault level with `T_source` and `T_sink` as covariates, compared
against a parameter sweep of the simulator.

| Fault | Agreement | Disagreement |
|---|---|---|
| Undercharge | 5/6 | `W_comp` |
| Condenser blockage | 4/5 | `subcooling` — measured **+**, simulated **−** |
| Indoor airflow | 3/5 | `superheat` and `T_discharge` both inverted |
| Overcharge | 0/0 | simulator produces no signal at all |

Three concrete modelling defects follow:

1. **Overcharge is not modelled.** Every simulated slope is zero — `simulator.py` only branches
   on `refrigerant_charge < 1.0`. `REFRIGERANT_OVERCHARGE` is declared but inert, and 942
   measured overcharge rows have no counterpart.
2. **Condenser-blockage subcooling runs backwards.** Blocking a condenser makes liquid
   accumulate and subcooling **rise** — which is what the measurements show. The simulator
   lowers it. `d_subcooling` is one of the model's five residual features.
3. **Evaporator airflow has two inverted signs.** Measured, reduced indoor airflow lowers
   superheat and discharge temperature. The `+ 8.0 * (1.0 - fan_evap_ratio)` pinch term pushes
   the other way.

## Residuals nearly double detection when the healthy reference is calibrated on the target machine

Gradient boosting, six classes, no target leakage. Healthy baseline for the residuals: median
of the five nearest fault-free tests in (`T_source`, `T_sink`) **within the same machine**.

| Feature set | Random CV | Leave-one-machine-out | F1 macro (LOMO) |
|---|---|---|---|
| Raw measurements | 0.954 | 0.333 | 0.282 |
| Raw + residuals | **0.973** | 0.562 | 0.423 |
| **Residuals only** | 0.937 | **0.602** | **0.479** |
| Residuals + conditions | 0.945 | 0.594 | 0.479 |

Every residual row uses a healthy reference calibrated on the target machine.
With a reference transferred from the training machine, “residuals only” falls from
0.602 to **0.318**.

Read the two columns against each other: **the feature set that scores best under random
cross-validation — raw + residuals, 0.973 — is not the one that transfers best.** Ranking
models on a random split would pick the wrong design.

Majority-class reference: 0.251.

**This is the empirical vindication of the Li & Braun residual design** that `src/fdd/features.py`
already names in its docstring. Residuals take detection from 0.333 to 0.602 **when the healthy reference is calibrated on the target machine**, at a cost of 1.7 points of same-machine accuracy. Without that calibration the transfer ceiling is **0.318**.

**Adding raw quantities back to the residuals hurts leave-one-machine-out detection**
(0.602 → 0.562), still with a target-calibrated reference: absolute values
let the model re-identify the machine. `FEATURE_COLUMNS` currently mixes 19 absolute quantities
with 5 residuals — worth revisiting.

**0.602 is not a transferable floor.** It requires fault-free data from the target machine. Rebuilt from the training machine only, the ceiling is **0.318** (F1 macro 0.290). A second-order polynomial with indoor dew point — the form NIST uses — reaches 0.302; a random forest reaches 0.265. No reference model tried lifts the ceiling.

## What this says about the reported metric

**0.95 under random cross-validation against 0.60 under leave-one-machine-out**, on the same
data and the same model. A random split measures the installation as much as the fault.

That is the same failure mode as training and testing from one simulator, in a different guise
— and here it is measured rather than argued. Any accuracy figure this project reports should
name its validation protocol.

## Calibration budget: how many healthy tests?

Protocol (leave-one-machine-out, both directions, mean): `GradientBoostingClassifier(random_state=42)`
trained **only** on the training machine; eight residuals; kNN healthy reference
(`k = min(5, n)`) in (`T_source`, `T_sink`). `n` healthy tests are drawn from the **test**
machine to build that reference. Those `n` rows are **held out of the test set** — otherwise
`No_Fault` is scored on the same points that defined the yardstick. Twenty random draws
(seeds 0–19); mean and 10th/90th percentiles. `n = 0` and `n = all` are the published
endpoints and are deterministic.

Controls recovered exactly: `n = 0` → **0.318 / 0.290**; `n = all` → **0.602 / 0.479**.

| n healthy (target machine) | Accuracy | p10–p90 | F1 macro |
|---|---|---|---|
| 0 (reference transferred) | 0.318 | — | 0.290 |
| 1 | 0.290 | 0.204 – 0.401 | 0.271 |
| 5 | 0.314 | 0.226 – 0.382 | 0.289 |
| 10 | 0.377 | 0.345 – 0.404 | 0.324 |
| 20 | 0.409 | 0.378 – 0.438 | 0.349 |
| 50 | 0.456 | 0.438 – 0.474 | 0.380 |
| all (~625–727) | 0.602 | — | 0.479 |

90 % of the gap 0.318 → 0.602 is **0.574**. No finite `n` on the grid reaches it.
**n = 50 recovers about 49 % of the gain.** Getting to 90 % takes essentially the full
healthy set of the target machine.

Spreading the `n` points over the (`T_source`, `T_sink`) envelope, rather than drawing at
random, helps most when `n` is small (n = 5: **0.391** vs 0.314). The gap shrinks as `n`
grows. Field reading: a handful of commissioning tests is not a calibration; coverage of the
operating season is.

Notebook and figure: `EDA/EDA_NIST_calibration.ipynb`, `docs/calibration_budget.png`.
