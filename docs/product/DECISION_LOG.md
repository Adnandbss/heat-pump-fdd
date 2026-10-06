# Decision log

> **Status:** Measured — every decision points to the logged evidence behind it. Dates come from the git history; where a decision spanned several commits, the month is given.

| Date | Decision | Evidence | What it changed |
|---|---|---|---|
| Sep 2026 | Withdraw the first headline accuracy | X0/leaked-dCOP 0.996 came from a label leak: `d_COP` was zero on every healthy row and on no other. After the fix, X0/holdout-test is 0.893 | The README publishes both numbers side by side. Every figure now names its protocol |
| Sep 2026 | Ship Random Forest, not Gradient Boosting | Tied on validation; on X0/holdout-test, Random Forest 0.893 and Gradient Boosting 0.899, inside each other's interval | Cheaper inference and readable importances won a tie the test set could not break |
| Sep 2026 | Treat the validation protocol as part of every result | Same data, same classifier: X0b/random-cv 0.954, X0b/LOMO 0.333 on raw measurements | `tests/test_docs.py` rejects a published figure without its protocol |
| 2026-09-18 | Remove the valve-leak class | The simulator has no physics for it; its samples were a mix of two other faults | Seven classes, not eight. Valve-leak physics is roadmap R4, unprioritised |
| 2026-09-19 | Dispatch on charge faults only | X5/sim2real F1: undercharge 0.445, overcharge 0.522, condenser fouling 0, evaporator fan 0.031 | The evidence gate in `api/fleet_policy.py` (2026-10-06) |
| 2026-09-20 | Treat calibration as a deployment constraint | X1/LOMO-calibration-n50 0.456 and X1/LOMO-calibration-n10 0.377, against X0b/LOMO 0.602 with the full healthy reference | Commissioning-baseline capture is a requirement in the [PRD](PRD.md) and second in [STRATEGY.md](STRATEGY.md) |
| 2026-10-01 | Park failure prediction | No public dataset follows a heat pump from healthy to a dated failure. Candidates checked: NIST, ASHRAE RP-1043, the LBNL collection, the gradual-fault AHU set, the propane heat-pump bench — all fixed-severity files or steady-state tests | No remaining-useful-life model. The roadmap grand 2 stays closed until such data exists |
| 2026-10-06 | Gate fleet dispatches on measured evidence, read at request time | Same X5/sim2real rows | An ML fix logged on `main` changes the triage with no product release. `FDD_FLEET_VALIDATED_ONLY` keeps the comparison available |
| 2026-10-06 | Choose the OEM after-sales team as the first user | Not measured. It is the buyer that owns a connected fleet and pays for wasted visits | Discovery starts there ([RESEARCH_KIT.md](RESEARCH_KIT.md)) |

## Decisions not taken yet

- Whether a low-confidence alert should go to the installer at all, or stay internal.
- Whether the healthy reference is per unit or per product line.
- The confidence threshold, to be set from shadow-mode visit outcomes.
