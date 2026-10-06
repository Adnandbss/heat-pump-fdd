# Strategy — objective, priorities, MVP, KPIs

> **Status:** Plan — reach and impact are assumptions; confidence is anchored on `outputs/results.csv`. No KPI below has been measured.

## Pilot objective and key results

**Objective.** Show that evidence-gated alerts make refrigerant-charge visits worth the truck roll for one OEM service team.

| Key result | How it is measured |
|---|---|
| KR1. Five interviews done, and assumptions A1 to A4 updated, before the pilot starts | Synthesis grid in [RESEARCH_KIT.md](RESEARCH_KIT.md) |
| KR2. Eight weeks of shadow mode on one product line, with the installer logging the fault found on every visit | Visit outcome logged against the alert |
| KR3. Dispatch precision of gated alerts above the team's current baseline for charge-related visits | Baseline taken during the first two weeks of shadow mode |
| KR4. No dispatch on a fault class without measured evidence | Enforced by the gate, checked by `tests/test_fleet.py` |

## Prioritisation — RICE

Reach is the number of units affected per quarter in an assumed 1,000-unit pilot fleet. Impact uses a 1-to-3 scale. Effort is in person-weeks. Score = reach × impact × confidence ÷ effort.

| Item | Reach | Impact | Confidence | Effort | Score | Why this confidence |
|---|---|---|---|---|---|---|
| Fleet triage with the evidence gate (MVP) | 1000 | 2 | 50 % | 2 | 500 | Charge transfers in X5/sim2real, but no user has seen it |
| Commissioning baseline capture | 250 new installs | 3 | 80 % | 6 | 100 | Calibration effect measured: X1/LOMO training-machine 0.318 against X0b/LOMO 0.602 |
| Failure prediction (remaining useful life) | 1000 | 3 | 5 % | 12 | 13 | No public dataset with a dated failure (roadmap, grand 2) |
| Condenser-fouling physics (roadmap R5) | 50 | 2 | 20 % | 8 | 3 | X5/sim2real condenser fouling F1 is 0; the fix is uncertain science |
| Valve-leak physics (roadmap R4) | 30 | 1 | 30 % | 4 | 2 | Class removed for lack of physics; never measured |

Not scored, because they carry no user value on their own: repository hygiene and the mixed English and French interface (roadmap R3).

The order the table gives — triage first, commissioning capture second, physics later, prediction parked — is the order of this track.

## MVP scope — MoSCoW

| | Scope |
|---|---|
| **Must** | Service queue sorted by action. Dispatch only on classes that transfer in X5/sim2real. An evidence badge with its source on every row. An engineering-review route for the rest. A feature flag for the gate. A notice that the demo fleet is simulated |
| **Should** | Monitor action for low confidence, including a low-confidence "Normal". Count of dispatches held back by the gate. A fault-specific instruction for the installer |
| **Could** | Ground-truth toggle for demos. Export of a row to a service ticket. Filtering by product line |
| **Won't, this release** | Failure prediction. Dispatch on condenser fouling or the evaporator fan. A homeowner app. Automatic scheduling of visits |

## KPIs

| KPI | Definition | Role |
|---|---|---|
| Dispatch precision | Share of dispatched visits where the installer confirms the predicted fault | North star |
| False dispatches | Visits that find no fault, per 100 units per month | Counter-metric: the cost the gate exists to cut |
| Missed charge faults | Charge faults found by a complaint or a routine visit with no prior alert, per 100 units per year | Counter-metric: the cost of gating too hard |
| Review backlog age | Median days a unit waits in engineering review | Guardrail: review must not become a bin |
| Baseline coverage | Share of units with a healthy reference captured at commissioning | Leading indicator for detection quality |

Targets are set from the shadow-mode baseline, not before it.
