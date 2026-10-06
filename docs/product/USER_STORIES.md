# User stories — Fleet triage

> **Status:** Measured — each acceptance criterion is checked by the test named next to it. A story without a passing test is not done.

## S1. Dispatch only on validated faults

*As a service engineer, I want a dispatch recommended only for faults the system can find on real machines, so that I do not send an installer on a guess.*

- **Given** a unit diagnosed with condenser fouling, evaporator fan fault or evaporator fouling at high confidence, **when** the gate is on, **then** its action is engineering review, not dispatch. — `tests/test_fleet.py::test_gate_never_dispatches_a_class_without_measured_evidence`
- **Given** the same unit, **when** the gate is off, **then** it is dispatched and counted as held back by the gated policy. — same test
- **Given** the fleet route, **when** it returns, **then** every dispatched unit has the evidence status *transfers*. — `tests/test_fleet.py::test_fleet_route_gates_dispatch_and_reports_what_it_held_back`, and in the browser `web/e2e/fleet.spec.ts`

## S2. Evidence comes from the results log, not from code

*As the product owner, I want the gate to follow the logged evidence, so that an ML improvement changes the product without a product release.*

- **Given** `outputs/results.csv`, **when** the policy reads it, **then** charge faults transfer, condenser fouling and the evaporator fan do not, and evaporator fouling is untested. — `tests/test_fleet.py::test_evidence_status_reads_results_csv`
- **Given** a better logged F1 for condenser fouling, **when** the queue is computed, **then** a confident condenser-fouling unit is dispatched. — `tests/test_fleet.py::test_a_better_logged_f1_flips_condenser_fouling_to_transfers`
- **Given** no results log at all, **when** the queue is computed, **then** nothing is dispatched. — `tests/test_fleet.py::test_missing_results_log_dispatches_nothing`

## S3. Tell the installer what to do

*As an installer, I want a dispatch to say what to check, so that I bring the right equipment.*

- **Given** a confident undercharge diagnosis, **when** it is dispatched, **then** the instruction is the leak-search-and-recharge instruction. — `tests/test_fleet.py::test_validated_fault_with_confidence_is_dispatched_with_an_instruction`

## S4. Do not act on, or clear, an uncertain diagnosis

*As a service engineer, I want uncertain diagnoses flagged for a re-check, so that a low-confidence "healthy" does not hide a fault.*

- **Given** a validated fault or a Normal diagnosis below the confidence threshold, **when** the queue is computed, **then** the action is monitor. — `tests/test_fleet.py::test_low_confidence_is_monitored_not_dispatched_nor_cleared`
- **Given** a confident Normal diagnosis, **then** the action is no action. — `tests/test_fleet.py::test_confident_healthy_unit_needs_no_action`

## S5. See the most urgent units first

*As a service engineer, I want the queue sorted by what needs doing, so that the morning triage starts at the top.*

- **Given** units with every action, **when** the queue is returned, **then** the order is dispatch, review, monitor, no action, and the summary counts add up to the number of units. — `tests/test_fleet.py::test_summary_counts_match_rows_and_order_follows_priority`

## S6. A demo that does not move under you

*As a presenter, I want the same demo fleet every time, so that the walkthrough in [DEMO_SCRIPT.md](DEMO_SCRIPT.md) stays true.*

- **Given** the same seed, **when** the fleet is built twice, **then** the units are identical. — `tests/test_fleet.py::test_fleet_is_deterministic_for_a_seed`
- **Given** the Fleet page, **when** it loads, **then** rows render with no `NaN` and at least one engineering-review row. — `web/e2e/fleet.spec.ts`

## Refinement

This project has one contributor. There was no refinement meeting, and estimates are mine: two person-weeks for S1 to S6, the effort used in [STRATEGY.md](STRATEGY.md).
