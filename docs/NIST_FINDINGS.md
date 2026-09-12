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

## Residuals nearly double cross-machine transfer

Gradient boosting, six classes, no target leakage. Healthy baseline for the residuals: median
of the five nearest fault-free tests in (`T_source`, `T_sink`) **within the same machine**.

| Feature set | Random CV | Leave-one-machine-out | F1 macro (LOMO) |
|---|---|---|---|
| Raw measurements | 0.954 | 0.333 | 0.282 |
| Raw + residuals | **0.973** | 0.562 | 0.423 |
| **Residuals only** | 0.937 | **0.602** | **0.479** |
| Residuals + conditions | 0.945 | 0.594 | 0.479 |

Read the two columns against each other: **the feature set that scores best under random
cross-validation — raw + residuals, 0.973 — is not the one that transfers best.** Ranking
models on a random split would pick the wrong design.

Majority-class reference: 0.251.

**This is the empirical vindication of the Li & Braun residual design** that `src/fdd/features.py`
already names in its docstring. Residuals take cross-machine transfer from 0.333 to 0.602 and
cost 1.7 points of same-machine accuracy.

**Adding raw quantities back to the residuals hurts transfer** (0.602 → 0.562): absolute values
let the model re-identify the machine. `FEATURE_COLUMNS` currently mixes 19 absolute quantities
with 5 residuals — worth revisiting.

The nearest-neighbour baseline is deliberately crude; a fitted reference model over the
fault-free tests, as NIST itself builds, should do better. **0.602 is a floor.**

## What this says about the reported metric

**0.95 under random cross-validation against 0.60 under leave-one-machine-out**, on the same
data and the same model. A random split measures the installation as much as the fault.

That is the same failure mode as training and testing from one simulator, in a different guise
— and here it is measured rather than argued. Any accuracy figure this project reports should
name its validation protocol.
