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

## Sign agreement: 20 / 22 (91 %)

Each quantity regressed on fault level with `T_source` and `T_sink` as covariates, compared
against a parameter sweep of the simulator. Zero simulated slopes are scored `∅` and do not
enter the total.

Was 12 / 16 before four simulator fixes (discharge cap, overcharge branches, condenser-fouling
subcooling sign, evaporator-fan superheat / discharge signs).

| Fault | Agreement | Disagreement |
|---|---|---|
| Undercharge | 5/6 | `W_comp` — measured **+**, simulated **−** |
| Condenser blockage | 5/5 | — |
| Indoor airflow | 5/5 | — |
| Overcharge | 5/6 | `COP` — measured **+**, simulated **−** |

Overcharge now produces the four measured signs that were previously all `∅`: `subcooling +`,
`W_comp +`, `P_cond +`, `superheat −`. Two disagreements remain, neither of which was in the
P3 brief: undercharge compressor work, and overcharge COP.

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

That 0.318 → 0.602 is **not a uniform gain**. Which faults it actually buys is the next section.

## Which faults are actually detected

0.602 accuracy against 0.479 F1 macro — twelve points. The six classes are not detected
equally. Protocol unchanged from the calibration notebook: leave-one-machine-out, both
directions, residuals only, `GradientBoostingClassifier(random_state=42)`. Controls recovered
exactly (mean of the two folds): calibrated **0.602 / 0.479**, transferred **0.318 / 0.290**.
Counts: no-fault 1352, undercharge 1228, overcharge 942, indoor airflow 774, liquid line 593,
condenser blockage 497. Precision, recall and F1 below are means of the two directions;
the two confusion matrices are **not** added together.

Notebook and figures: `EDA/EDA_NIST_perclass.ipynb`,
`docs/nist_perclass_confusion.png`, `docs/nist_perclass_calibration.png`.

### Per class — calibrated reference (n = all)

| Fault | Precision | Recall | F1 | n |
|---|---|---|---|---|
| Undercharge | 0.748 | 0.961 | **0.832** | 1228 |
| No-fault | 0.722 | 0.837 | 0.741 | 1352 |
| Overcharge | 0.735 | 0.775 | 0.674 | 942 |
| Condenser blockage | 0.611 | 0.220 | 0.299 | 497 |
| Indoor airflow | 0.269 | 0.313 | 0.288 | 774 |
| Liquid line | 0.206 | 0.068 | **0.040** | 593 |

**Undercharge is the only fault a technician can trust.** F1 0.83 (0.91 on the 14 SEER unit,
0.76 on the 16). Precision and recall are both high in both directions.

**Liquid line is not detected.** F1 0.04. On the 16 SEER unit: 8 true positives out of 492
(recall 0.016). On the 14: recall 0.12 with precision 0.03 — the model just sprays the label.

**Indoor airflow is barely detected** (F1 0.29), **condenser blockage barely either**
(F1 0.30, recall 0.22). No-fault looks healthy only once the reference is calibrated
(see below). Overcharge is the odd one: it is already found without calibration.

### What confuses with what — physics, not the algorithm

The two machines have different mixes (856 undercharges / 114 overcharges on the 14 SEER,
372 / 828 on the 16), so the matrices must stay separate.

On the 14 SEER unit, **146 of 278 indoor-airflow tests are called liquid-line**, and
**129 of 344 condenser-blockage tests are called liquid-line** as well. Starving the
evaporator of air and restricting the liquid line both drop suction pressure and capacity;
blocking the condenser and overcharging both stack liquid on the high side and raise
subcooling. Those pairs share a physical signature. The residual vector does not split them.

On the 16 SEER unit the dominant leak is the other way: **304 of 828 overcharge tests are
called indoor airflow**, and **262 of 496 airflow tests are called no-fault**. Same
neighbourhood, different machine.

### The two leave-one-machine-out directions do not agree everywhere

No-fault recall is 0.69 one way and 0.99 the other. Overcharge precision is 0.47 one way
and 1.00 the other. Transferred to the 16 SEER unit, condenser blockage and liquid line are
**never predicted**. When a class fails in one direction only, that is a property of that
machine, not of the fault.

### Calibration does not help every fault

| Fault | F1 transferred | F1 calibrated | ΔF1 |
|---|---|---|---|
| No-fault | 0.131 | 0.741 | **+0.610** |
| Undercharge | 0.481 | 0.832 | +0.351 |
| Condenser blockage | 0.067 | 0.299 | +0.232 |
| Indoor airflow | 0.269 | 0.288 | +0.018 |
| Liquid line | 0.007 | 0.040 | +0.034 |
| Overcharge | **0.786** | 0.674 | **−0.111** |

Almost all of 0.318 → 0.602 is **learning to recognise a healthy machine**, plus
undercharge. Overcharge is found *better* with a transferred reference — its subcooling /
compressor-work signature survives the machine change, and calibration is not what it needs.
Indoor airflow and liquid line do not benefit. A calibration budget is only actionable if
it names **which fault** one is looking for.

## Does the learned model beat a sign table?

The residual FDD literature's baseline is a **sign table**: subcooling up and high-side
pressure up means condenser blockage. This project cites Li & Braun, builds the residuals,
then puts gradient boosting on top — without ever implementing the table.

Signs are estimated on the **training machine only**, same least-squares of fault level
with `T_source` and `T_sink` as covariates as the simulation/measurement agreement. No
threshold is searched on the test set. The voter scores `sum(sign(residual) × expected)`;
`No_Fault` wins when every fault score is ≤ 0. A depth-3 tree sits between a written rule
and the hundreds of trees in the boosting. Protocol otherwise unchanged: leave-one-machine-out,
both directions, eight residuals, `GradientBoostingClassifier(random_state=42)`. Controls
recovered exactly: calibrated **0.602 / 0.479**, transferred **0.318 / 0.290**.

Notebook and figure: `EDA/EDA_NIST_rules.ipynb`, `docs/nist_rules_vs_gb.png`.

| Method | Healthy reference | Accuracy | F1 macro |
|---|---|---|---|
| Gradient boosting | target kNN | **0.602** | **0.479** |
| Depth-3 tree | target kNN | 0.558 | 0.422 |
| Sign table | target kNN | 0.365 | 0.243 |
| Gradient boosting | train kNN | 0.318 | 0.290 |
| Depth-3 tree | train kNN | 0.287 | 0.230 |
| Depth-3 tree | train-healthy global median | 0.340 | 0.306 |
| Sign table | train kNN | 0.251 | 0.175 |
| Sign table | train-healthy global median | 0.245 | 0.197 |
| Majority class | — | 0.251 | — |

**Gradient boosting earns its place on the average**, by about 24 accuracy points against
the table when the healthy reference is calibrated. A single depth-3 tree is only four
accuracy points and six F1 points behind the boosting — the hundreds of trees buy something,
not a gulf.

**Without a condition-matched healthy reference the table is worth nothing** (0.245 / 0.197):
the majority class. A sign rule needs a deviation from a healthy cycle *at the equivalent
condition*. That is what justifies Li & Braun, not the boosting. The hope that directions
alone would hold near 0.45 with no calibration is rejected.

**Transferred, the table falls back to the class mix** (0.251). Indoor-airflow signs invert
from one machine to the other, so there is no universal table to extract from this campaign.
A table frozen on both machines would leak the test unit; each fold only sees its own.

### Per class — calibrated reference

| Fault | GB | Depth-3 tree | Sign table |
|---|---|---|---|
| Undercharge | 0.832 | **0.905** | 0.594 |
| No-fault | **0.741** | 0.655 | 0.113 |
| Overcharge | **0.674** | 0.576 | 0.440 |
| Condenser blockage | **0.299** | 0.183 | 0.072 |
| Indoor airflow | **0.288** | 0.127 | 0.102 |
| Liquid line | 0.040 | 0.087 | **0.136** |

**Liquid line is the one fault where the table beats the model** (F1 0.136 against 0.040
for the boosting, 0.087 for the tree). Still weak, but it is the class the boosting learned
to ignore and the physics still names.

**Undercharge does not need hundreds of trees.** The depth-3 tree (F1 0.91) beats even the
boosting (0.83): a threshold on two or three residuals is enough. The learned model earns
its keep mainly on **no-fault** and, to a lesser extent, overcharge — where a single
direction does not split the classes.

## Stage 1: the healthy-reference estimator

The published 0.602 is a **kNN, k=5, median**, in `(T_source, T_sink)`, on healthy tests of
the **target** machine. Stage 2 was benchmarked in X2. Stage 1 was not. Classifier frozen
(`GradientBoostingClassifier(random_state=42)`, train residuals = that same kNN on
train-healthy). Only the test-time estimator varies. Control recovered exactly:
**0.602 / 0.479**.

`KNeighborsRegressor` (sklearn default = **mean**) scores **0.554**, not 0.602. The project's
median is worth 4.8 points. `dmin` is Euclidean, the same metric as the tree.

**28 % of faulty tests have a healthy neighbour within 0.1 °C** (72 % within 0.5 °C). The
campaign is replicated by construction.

| Estimator (target-machine healthy, no dew) | dmin=0 | dmin=0.5 °C |
|---|---|---|
| kNN k=5 median — **published** | **0.602** | **0.482** |
| kNN k=1 median | 0.650 | 0.501 |
| kNN k=5 mean | 0.554 | 0.485 |
| Global median | 0.337 | 0.336 |
| Linear / poly2 / ridge | ~0.46 | ~0.46 |
| Random forest | 0.513 | — |

The curve is monotonic. A small `k` looks ten points better until replicas are forbidden;
then k=1 and k=5 sit on the same step. Fitted surfaces are flat in `dmin`: they never used
the twins, and they never reach 0.602.

Indoor dew point in the kNN **of both stages** (train and test) drops accuracy
**0.602 → 0.576**. Leave-one-out MAE on healthy tests improves slightly. Judging stage 1 on
regression error would have picked the variant that loses at the end of the chain.

Per class, kNN k=5: no-fault F1 **0.735 → 0.434** at dmin=0.5 °C. Undercharge stays
(0.854 → 0.841). The 12 accuracy points are mostly “recognising a healthy twin”.

**Verdict.** 0.602 **holds as the chamber-protocol number** (a healthy test exists at the
same condition). It **does not hold** as the project's reference performance on a unit in
service. The preliminary 0.511 is superseded by **0.482**. Numbers:
`outputs/results.csv` (`experiment=X3`), `outputs/x3_estimator_dmin.csv`. Notebook and
figure: `EDA/EDA_NIST_reference_bench.ipynb`, `docs/nist_x3_dmin.png`.

**0.602 is not replaced in this change.** If the field-like protocol becomes the headline,
these five citations must move together in a separate PR:

- `README.md` — residuals-only LOMO **0.602**
- `docs/DOSSIER.md` (+ `docs/DOSSIER.pdf`)
- `docs/ROADMAP.md`
- `docs/NIST_FINDINGS.md` — this file, every 0.602 above this section
- `outputs/results.csv` — `X0b` / `LOMO` / `target-machine` / `residuals` / `accuracy`

## Does the simulator describe reality? (X5)

**No. It describes itself.** A model that scores **0.921 [0.906 – 0.933]** on simulated
hold-out at NIST conditions falls to **0.454 [0.435 – 0.472]** on the measured tests.
The same five-class task trained on measured data reaches **0.668 [0.650 – 0.685]**
(LOMO). The drop is the simulator, not the task.

The 5.3 % domain overlap was a sampling limit, not a physical one. The simulator runs
at NIST conditions. At 24 / 35 °C it reports `P_evap` 14.04 bar, τ 1.72, COP 4.32;
healthy NIST tests sit at **10.5 bar, 2.37, 3.41**. Aspiration is 35 % high, the
compression ratio 28 % low, COP 27 % optimistic. Residuals built on those scales
do not live in the same space as residuals built on a measured kNN (k=5, median,
X3 protocol).

`T_evap` is capped at 20 °C. That bound is hit from `T_source = 25 °C` on a healthy
cycle (the brief's 27 °C threshold was one step late). Comparison is therefore
restricted: simulated training in `T_source ∈ [14, 24.9]`, `T_sink ∈ [19, 48]`,
speed 1.0; measured test at `T_source ≤ 26 °C` (4356 / 7375 rows, 59 %). No
generated `T_evap` sits on 20.0. The cap itself was not raised — that would be a
physics change and would invalidate the simulated scores.

Five classes correspond. Liquid-line tests are dropped (unmodelled). Simulated
evaporator fouling and condenser-fan faults are dropped (absent from NIST). In
cooling, the outdoor coil is the condenser: NIST `CF` maps to `Condenser_Fouling`,
not evaporator fouling.

| Protocol | Accuracy | 95 % Wilson | F1 macro | Majority | n |
|---|---|---|---|---|---|
| Simulated → simulated (hold-out) | **0.921** | 0.906 – 0.933 | 0.917 | 0.400 | 1500 |
| **Simulated → measured** | **0.454** | **0.435 – 0.472** | **0.343** | 0.281 | 2846 |
| Measured → measured (LOMO) | **0.668** | 0.650 – 0.685 | 0.596 | 0.281 | 2846 |

Charge is the only fault that partially transfers (overcharge F1 0.52, undercharge
0.45). Condenser blockage and indoor airflow do not (F1 0.00 and 0.03) — and they
are already the hard classes on measured LOMO (0.32 and 0.40). No-fault recall on
transfer is 0.94: the model mostly says *Normal*.

The simulator is a demonstration and exploration tool. It is not a source of
training labels for a field detector. Numbers: `outputs/results.csv` (`experiment=X5`),
`outputs/x5_sim2real.csv`. Notebook and figure: `EDA/EDA_sim2real.ipynb`,
`docs/nist_x5_sim2real.png`. Compute: `EDA/x5_compute.py`.
