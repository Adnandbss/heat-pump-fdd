# Roadmap

Where the project stands after the architecture cleanup and the confrontation with the NIST
data, and what is left. The reference documents are
[ARCHITECTURE](ARCHITECTURE.md), [NIST_MAPPING](NIST_MAPPING.md), and
[NIST_FINDINGS](NIST_FINDINGS.md). This roadmap is a working document.

## What is done

**Setup** — `.gitignore` cleaned, Docker, front CI, and above all the pin `scikit-learn==1.6.1`,
without which the committed `.joblib` does not load.

**Layered architecture** (PR #2, #3, #4) — `src/` went from nine flat modules to three
explicit layers:

```
physics/   the physical model        simulator · thermo_lab · thermodynamic_viz
fdd/       the shared method         features · ml_models · inference · visualization
studies/   the studies               synthetic/ (generator · scenarios · taxonomy)
outputs/<study>/   models/<study>/
```

Rule: `studies/` → `fdd/` → `physics/`. Zero violations today, and five tests lock it
(`test_engine_has_no_synthetic_study_api`, and the rest).

**76 tests** pass (including the P0 integrity guards and the P4 taxonomy check). Behavioural
equivalence was checked at every refactor step by comparing outputs before and after, byte
for byte.

**Confrontation with the NIST tests** — four notebooks in `EDA/` (descriptive, model,
reference, calibration), results in `docs/NIST_FINDINGS.md`.

**Four physics bugs fixed** — overcharge not modelled, subcooling reversed on condenser
fouling, superheat and discharge reversed on the evaporator fan, discharge ceiling declared
and never applied. Agreement of the signs of variation with the measured tests goes from
**12/16 to 20/22**, and simulated accuracy from 99.8% to 99.6% — an expected drop: the model
no longer learns impossible cycles. **P0** then closed four pipeline leaks: the honest
simulated figure is **91.9% [90.4 – 93.1]** (hold-out, selection on val).

**Presentation dossier** — `docs/DOSSIER.md` and its PDF: the system module by module,
equations, commented figures, and the known limits.

## What the NIST data taught

Detail and method in [NIST_FINDINGS](NIST_FINDINGS.md). Three things matter here.

**1. The validation protocol changes everything.** On 5386 real tests, six classes, the same
model:

| Validation | Healthy reference | Accuracy |
|---|---|---|
| Random CV (mixes the machines) | target machine | **0.95** |
| Leave-one-machine-out | target machine (calibrated) | **0.602** |
| Leave-one-machine-out | training machine (transferred) | **0.318** |

The **0.602 is itself conditional.** It assumes a healthy measurement at nearly the same
conditions as the fault — true in the NIST campaign, replicated by construction, false on a
machine in service. Forbidding neighbours closer than 0.5 °C drops it to **0.482** (X3).
README / dossier / `NIST_FINDINGS` / `results.csv` (`X0b`) still cite it without that warning:
a separate PR.

A random split measures the installation as much as the fault. It is the same problem as
training and testing on the same simulator — except here it is **measured**.

**2. The residual design is validated, and it is the project's best argument.** Residuals
take detection from **0.333 to 0.602 when the healthy reference is calibrated on the target
machine**, for 1.7 points lost in random CV. Without that calibration, transfer caps at
**0.318**. The Li & Braun method named in `src/fdd/features.py` holds on real measurements.

Corollary: **adding the raw quantities to the residuals degrades transfer** (0.602 → 0.562),
because the absolute values let the model re-identify the machine.

**3. Four physics errors in `simulator.py`**, found by comparing the signs of the measured
and simulated signatures. Fixed: agreement goes from **12/16 to 20/22**.

| Fault | What was wrong | After the fix |
|---|---|---|
| Overcharge | not modelled — all slopes zero | `subcooling +`, `W_comp +`, `P_cond +`, `superheat −` |
| Condenser blockage | `subcooling` reversed | rises, as measured |
| Evaporator airflow | `superheat` and `T_discharge` reversed | both fall |
| `T_discharge_max = 130` | declared, never applied (319 °C at −10/55) | capped over the whole training domain |

Two disagreements remain: `W_comp` undercharge, `COP` overcharge. Overcharge is now in the
mix (500 / 5000). Valve leak is not modelled: it would need a `volumetric_efficiency_loss`
parameter (hot discharge gas back to suction) — simulator debt, not a generator flag.

## Decisions that belong to you

**A. How to announce performance.** This is the most urgent point, and the only one a jury
will take apart in one question. The current 89.3% (30% hold-out, selection on val, Wilson
interval 87.6 – 90.7, seven classes) measures how separable the signatures are inside the
physical model, not detection on a real machine. The previous 99.6% was a label leak.
Proposal:

**Frozen**, now that X3 and X5 have been run:

> Fault signatures separable at **89.3% [87.6 – 90.7]** in hold-out on simulated data
> (seven classes, selection on val, sklearn `Pipeline`) — a measure of separability inside the
> physical model, not of detection on a machine.
>
> Confronted with the 7375 NIST tests: **0.602** when the healthy reference is calibrated on
> the target machine, **0.318** without that calibration (0.251 for the majority class), and
> 0.95 in random validation — which overstates by a factor of three.
>
> Trained on the simulator and tested on the real tests: **0.454**, refrigerant charge being
> the only fault that transfers (F1 0.45–0.52) and condenser fouling transferring not at all
> (F1 0.000).

Less spectacular, and defensible. The five rungs are shown side by side on the dashboard
Evidence page (P7), each with its protocol.

**B. Should the project switch to the real data?** The 5386 NIST tests are enough to retrain.
But that changes the subject: **cooling** mode, **air-to-air** machine, NIST taxonomy. The
A7/W40 framing disappears, and with it the fouling / fan distinction. The simulator would not
be thrown away — it would become the **healthy reference model**, its real role in the Li &
Braun method. A substantive decision, not a refactor.

The dashboard sub-question is settled: **P7 makes it a piece of evidence**, not a shop window.
Six figures read `results.csv` through the API, and a test forbids any hardcoded figure in
the TSX.

**C bis. Derived quantities** — **done, absorbed by P0.** Noise is applied to the sensors,
then `COP`, `pressure_ratio`, `compression_ratio`, `delta_T_*` and `capacity_ratio` are
recomputed, and the healthy reference of the `d_*` residuals is noised independently. A
permanent test checks `compression_ratio = P_cond / P_evap` and that no residual is
identically zero on a class. `pressure_ratio` (a duplicate) was removed in **P5**.

**C. `FEATURE_COLUMNS` as residuals only?** — **measured, not applied (P5).** On NIST,
residuals alone beat raw + residuals because there are two machines. Here there is only one.
Residuals alone lose seven points (0.823 against 0.893). The contract stays at 23 columns.

**D. The two ghost faults** — **done, P4.** `REFRIGERANT_OVERCHARGE` is produced
(500 / 5000), after removing the parasitic `condenser_fouling` in the injection branch.
`COMPRESSOR_VALVE_LEAK` is removed: the simulator does not expose a volumetric-efficiency
loss, and the old branch was a mix of two other faults. Delivered figure:
**89.3% [87.6 – 90.7]** (seven classes), against 91.9% [90.4 – 93.1] on six.

## GRAND 1 — Diagnosis (FDD)

Everything below is diagnosis: naming a fault that is present. Grand 2 — prognosis on time
series — starts **only once grand 1 is finished**, and only if a suitable dataset exists.

### 1A bis. P0 — Pipeline integrity · **done**

Four leaks measured on the 99.6% — fixed, dataset regenerated, model retrained
(`scikit-learn==1.6.1`). Published figure: **91.9% [90.4 – 93.1]** hold-out test,
Random Forest selected on val (GB within 0.002 F1, split on inference).

| | Leak | Fix |
|---|---|---|
| 1 | `d_COP == 0` for the 2000 `Normal` rows, and only those | derived quantities recomputed after noise; healthy reference noised |
| 2 | `scaler.fit_transform(X)` before `cross_val_score` | `Pipeline([scaler, clf])` |
| 3 | Final CV on the full `df` | 5-fold on `X_train` only — F1 0.914 ± 0.009 |
| 4 | Selection on the test (5th decimal) | train / val / test; selection on val; Wilson next to the score |

Guards in `tests/test_pipeline_integrity.py`: consistent derived quantities, no residual
identically zero on a class, `d_COP` is no longer a perfect detector, shuffled labels →
majority-class score.

X4 can now be run without the label leak crossing the hold-out.
P5 (residuals + conditions contract, drop the duplicate `pressure_ratio`) is no longer
blocked by the noise on the derived quantities.

### 1A ter. P4 — The two ghost classes · **done**

`FaultType` declared eight classes; the dataset produced six.

**Overcharge — produced.** P3 had given it a physics (high pressure, subcooling rising,
superheat falling). X1 showed it is the only NIST fault detected at 0.786 without
calibration. The important fix is not adding it: it is removing
`condenser_fouling = severity * 0.2` from the injection branch, a leftover from when
overcharge had no physics. Without that, every overcharge contained a real fouling.

**Valve leak — removed.** No `volumetric_efficiency_loss` parameter in `simulate_cycle`.
The old branch mixed undercharge and evaporator fouling. Generating it would have created a
class that is literally two others. To be modelled later, on the physics side.

After regeneration (5000 rows, 7 classes): **89.3% [87.6 – 90.7]**, F1 0.872. Before
(6 classes): 91.9% [90.4 – 93.1]. Overcharge is detected (F1 0.88). Confusion with condenser
fouling: 11 / 150 and 9 / 150 — a physical residue (both raise P_cond), not the artificial
coupling. Guard: `tests/test_fault_taxonomy.py` (FaultType == dataset == metadata).

### 1A. Truth and hygiene

| | Work | State |
|---|---|---|
| P1 | Truth of the figures in the documentation | done |
| P2 | Calibration budget measured | done |
| P3 | Four physics bugs fixed, sign agreement 12/16 → 20/22 | done |
| P4 | Decision D: produce overcharge, settle valve leak | **done** |
| P5 | Feature contract: duplicate removed, residuals-only measured and **rejected** | **done** |
| P6 | Split `api/app.py` — 4 inference routes against 17 dashboard routes | **done** |
| P7 | The dashboard reads `results.csv`: Evidence page, zero hardcoded figures | **done** |

### 1B. The experiments

The project had only run the easiest experiment available. This section names them all,
**numbered in execution order** — not in the order the idea appeared.

"Detect a fault" is not one experiment. It is several:

| | Trained on | Tested on | What it measures | State |
|---|---|---|---|---|
| **X0** | simulated | simulated, hold-out | Can a classifier invert the simulator | done — **89.3% [87.6 – 90.7]** (7 cl.) |
| **X1** | measured | measured, other machine | **Which faults** are detected | **done** |
| **X2** | — | measured, other machine | Does ML beat a **rule table** | **done** |
| **X3** | measured | measured, other machine | Which **healthy-reference estimator** is best | **done** |
| **X4** | simulated | simulated, **unseen conditions** | Does the 91.9% survive outside the learned points | **done** — yes for the domain, **no for severity** |
| **X5** | simulated | **measured** | Does the simulator describe reality | **done** — **45.4%**, condenser fouling at **0.000** |

#### X1 — Which faults are actually detected · done

The mean 0.602 hid a very uneven system:

| Fault | F1, calibrated reference |
|---|---|
| Undercharge | **0.832** |
| No fault | 0.741 |
| Overcharge | **0.674** |
| Condenser blockage | 0.299 |
| Indoor airflow | 0.288 |
| Liquid line | **0.040** |

**Charge faults carry the whole result.** The liquid line is never detected — eight true
positives out of 492 tests in one direction — and it is also the only fault the simulator
does not model. Airflow and liquid line confuse each other heavily: both starve the
evaporator, so they look alike on the measured quantities.

And **overcharge is detected better without calibration than with it** (0.786 against
0.674), consistent in both transfer directions. The calibration budget therefore depends on
the fault being sought, and for one of them it is zero.

Notebook: `EDA/EDA_NIST_perclass.ipynb`.

#### X2 — Does the model beat a rule table · **done**

Boosting earns its place: 0.602 / 0.479 against 0.365 / 0.243 for the sign table
(calibrated reference). A depth-3 tree is only 4 accuracy points behind. Without a paired
healthy reference, the table falls back to the majority class (0.245). Detail and figure:
`docs/NIST_FINDINGS.md`, `EDA/EDA_NIST_rules.ipynb`.

#### X3 — Benchmark of the healthy-reference estimator · **done**

The 0.602 is a kNN k=5 median, target machine. The control is reproduced exactly. Without
conditioning (global median): **0.337**. Most of the gain is comparing **at equivalent
conditions**, not the subtraction itself.

**The `dmin → accuracy` curve is the result.** 28% of faulty tests have a healthy neighbour
within 0.1 °C. Forbidding neighbours closer than 0.5 °C:

| Estimator | Replicates allowed | dmin = 0.5 °C |
|---|---|---|
| kNN k=1 | 0.650 | 0.501 |
| kNN k=5 — **published** | **0.602** | **0.482** |

The small `k` only wins because of the test plan. The chamber 0.602 falls to **0.482** on a
machine in service. Exploration said 0.511; the clean measurement is 0.482.

Dew point in the two-stage kNN: **0.602 → 0.576**. The regression error improves;
classification falls. Judge stage 1 at the end of the chain.

The 0.602 **is not replaced** in README / dossier / NIST_FINDINGS / `results.csv` (`X0b`) —
a separate PR, listed in `docs/NIST_FINDINGS.md`. Notebook:
`EDA/EDA_NIST_reference_bench.ipynb`.

#### X4 — Hold-out on the operating domain · **done**

Same simulated set, split by region instead of a random draw. Control: the X0 protocol
replayed in the same conditions (0.919).

| Split | Accuracy | 95% Wilson | n |
|---|---|---|---|
| Random (control) | 0.919 | 0.904 – 0.931 | 1500 |
| `speed > 0.85` | 0.920 | 0.902 – 0.935 | 1077 |
| GroupKFold 5 folds | 0.911 | 0.903 – 0.919 | 5000 |
| `T_amb < −5 °C` | 0.893 | 0.870 – 0.913 | 804 |
| `T_sink > 48 °C` | 0.889 | 0.871 – 0.904 | 1366 |

**The hypothesis is refuted: the score does not collapse.** Removing an entire region of the
domain costs at most 3 points. The 91.9% was not memorisation of operating points — it is
the only result of the campaign that vindicates the model.

The fragility is elsewhere. Hold-out on **severity**, four classes, fans excluded:

| Trained on | Tested on | Accuracy | F1 macro |
|---|---|---|---|
| Normal + severe | emerging faults | 0.428 | 0.496 |
| Normal + emerging | severe faults | 0.469 | 0.540 |

Binary detection alone: 0.762 and 0.887. **The model knows something is happening. It no
longer knows what.** That is the useful limit to announce: an FDD that does not extrapolate
in severity is useless for preventive maintenance, which lives precisely in emerging faults.

Measurements in 24 columns, so they predate P5. Logged under `X4`, eight protocols.

#### X5 — Simulated at NIST conditions, tested on the real tests · **done**

The 5.3% domain overlap was **a sampling obstacle, not a physics one**. Ranges widened,
dataset regenerated at NIST conditions, trained on it, tested on the real tests.

| | Accuracy | F1 macro |
|---|---|---|
| Simulated hold-out (reference) | 0.921 | 0.917 |
| **sim2real** — trained simulated, tested measured | **0.454** | **0.343** |
| LOMO on measured alone (reachable ceiling) | 0.668 | 0.596 |

By class, in sim2real:

| Class | Simulated F1 | F1 on the real tests |
|---|---|---|
| Undercharge | 0.974 | 0.445 |
| Overcharge | 0.936 | 0.522 |
| Normal | 0.930 | 0.716 |
| Evaporator_Fan_Fault | 0.998 | 0.031 |
| **Condenser_Fouling** | 0.749 | **0.000** |

**The simulator transfers on charge and on nothing else.** Condenser fouling, which it claims
to separate at 0.749, is never found on the real tests: its simulated signature is not that
of a real fouling. The evaporator fan fault, at 0.998 in simulation, falls to 0.031.

This is the harshest experiment of the campaign and the most useful. It says which part of
the simulator is publishable — charge — and which is a modelling artefact.

### Where things stand

The seven work items are delivered and the six experiments have been run. **The scope of
grand 1 is closed.** `X3-prelim` (6 rows) is not a ninth experiment to cover: it is the
preliminary pass that `X3` (505 rows) replaces. The figures leave it out on purpose
(`EXCLUDED_FROM_FIGURES` in `api/routers/evidence.py`).

```
P0 P1 P2 P3 P4 P5 P6 P7   ── delivered
X0 X1 X2 X3 X4 X5         ── run
G  guards                 ── delivered
```

What the campaign established, in the order that matters:

1. **The protocol weighs more than the model.** 0.954 in random CV against 0.333 in
   leave-one-machine-out, same data, same classifier. Every figure in the repository now
   names its protocol.
2. **Residuals double transfer** (0.333 → 0.602), but only with a healthy reference
   calibrated on the target machine. Transferred reference: 0.318, against 0.251 for the
   majority class.
3. **The simulator transfers only on charge.** X5: 0.454 overall, condenser fouling at
   0.000.
4. **The domain is not the problem. Severity is.** X4: at most 3 points lost by removing an
   entire region of the domain, but 0.43 when extrapolating severity.
5. **The shop-window figure went from 99.6% to 89.3%** as the leaks fell, and both numbers
   are published side by side.

### What remains

Nothing blocking. In order of value:

| | Work | Cost |
|---|---|---|
| R1 | ~~Replay and log the calibration sweep.~~ **Done** — `X1` / `LOMO-calibration-n{10,50}`. | — |
| R2 | ~~Check `GET /api/thermo/cop`.~~ **Done** — heating Carnot, Normal COP by bin, sweep at \(T_\mathrm{sink}-10\). | — |
| R3 | **Settle the 14 MB of binaries** from the P7 PR (`FRONT_EVIDENCE.pdf` + 9 PNGs) for a 53 MB `.git`, and the mixed English/French in the UI. | 1 h |
| R4 | **Model valve leak** on the physics side (`volumetric_efficiency_loss` in `simulate_cycle`), the only `FaultType` class removed for lack of physics. | 1 day |
| R5 | **Fix condenser fouling in the simulator**, the only fault at 0.000 in sim2real. The most interesting scientific item, and the most uncertain. | ? |

R1 and R2 are debts of honesty: to do before any presentation. R3 is cosmetic.
R4 and R5 open a new scope — they do **not** fit inside grand 1.

### Stopping rule

Every experiment suggested a new one. That is healthy, and it is endless.

**The scope of grand 1 was frozen at X0–X5 and P0–P7. It is reached.** Any question raised
since then goes into "what remains" above, not into the current scope.

### What the project delivers

Not a detector. **A validation methodology**: how to establish what an FDD model trained on
a simulator is worth, and what remains of it against 7375 chamber tests.

That is what should be announced. The raw performance — 89.3% — is the least interesting
figure in the repository, and the dashboard now shows it next to the other five rungs of
the ladder.

## GRAND 2 — Prognosis on time series

**Not started, and conditional on obtaining a suitable dataset.**

The NIST tests are **stationary**: a fault imposed and held, measured at equilibrium. There
is no clock, no progressive degradation, and no failure instant. Applying a temporal model
to them would invent a time axis that does not exist — exactly the kind of result this
project is built not to produce.

Eliminating criteria for a usable dataset: regular timestamps over months, at least one
dated terminal event per unit, outdoor conditions recorded, several units.

Acceptable sources, in order of preference: field history or an instrumented bench; failing
that, an out-of-domain reference dataset, clearly labelled as a method study; as a last
resort a **simulated** degradation, presented as such.

Prognosis is not a different model from diagnosis. It is a different **dataset**.

## Working rules

**The figures.** Every measured value is written to `outputs/results.csv` via
`tools.results.log`, never left only in a notebook output. The `protocol` and `reference`
columns are mandatory: **a number without its protocol is not a result**, and this project
has measured how much that matters (0.95 against 0.60 depending on the split; 0.602 against
0.482 depending on the structure of the test plan).

Documentation cites that file rather than retyping the values. The two contradictions that
had to be repaired — the dossier against the roadmap, then the 0.602 announced without its
condition — both came from manual copying.

**The plots.** An expensive notebook writes its results before it plots. The calibration
budget curve had to be redrawn; without the table that happened to remain in a cell output,
280 trainings would have been needed to fix a legend.

**The automatic guards.**

| Test | What it prevents |
|---|---|
| `tests/test_docs.py` | a document citing a file that disappeared after a refactor |
| `tests/test_docs.py` | a performance announced without naming its protocol |
| `tests/test_results_log.py` | a measurement logged without a protocol, or twice with two values |

**The repository.**

1. One PR = one idea, commit by commit.
2. `pytest` green before and after each PR — 43 today.
3. Nothing that breaks clone-and-run.
4. The pin `scikit-learn==1.6.1` is **load-bearing**: the committed `.joblib` loads only
   with that version. Changing it requires retraining via `main_analysis.py`.
5. `scripts/` is covered by no test — check it by hand after any move.
