# Product track

> **Status:** Mixed — every document below opens with its own status.

This folder treats the repository as a product for one user: the after-sales service team of a heat-pump manufacturer (OEM) watching an installed fleet. Start with the [case study](CASE_STUDY.md).

## How to read the statuses

| Status | Meaning |
|---|---|
| Measured | Backed by a row in `outputs/results.csv` or by code and tests in this repository |
| Hypothesis | Written before any user was interviewed. To be confirmed or killed by discovery |
| Plan | Something that has not happened yet: a launch, a pilot, a rollout |
| Template | An empty instrument to fill in: interview notes, usability results |
| Desk research | Public sources, read and linked, not checked with the vendors |

No interview, usage figure or launch result in this folder has happened unless it is marked `Measured`. The repository rule — a number without its protocol is not a result — applies to the product documents too, and `tests/test_docs.py` enforces it.

## The six stages

| Stage | Document | Status |
|---|---|---|
| 1. Discovery | [DISCOVERY.md](DISCOVERY.md): problem, assumptions, opportunity solution tree | Hypothesis |
| | [RESEARCH_KIT.md](RESEARCH_KIT.md): recruiting, interview guide, usability script, synthesis grid | Template |
| | [MARKET.md](MARKET.md): OEM installer tools and building FDD platforms | Desk research |
| 2. Scoping and strategy | [STRATEGY.md](STRATEGY.md): pilot objective, RICE, MVP in MoSCoW, KPIs | Plan |
| 3. Design | [PRD.md](PRD.md), sections *User flow* and *Feasibility* | Mixed |
| 4. Definition | [PRD.md](PRD.md) and [USER_STORIES.md](USER_STORIES.md) | Measured |
| 5. Delivery | [DECISION_LOG.md](DECISION_LOG.md); QA is CI plus `tests/test_fleet.py` and `web/e2e/fleet.spec.ts` | Measured |
| 6. Launch and iteration | [GTM_AND_LAUNCH.md](GTM_AND_LAUNCH.md): positioning, pilot, rollout, decision criteria | Plan |

Demo: [DEMO_SCRIPT.md](DEMO_SCRIPT.md), a two-minute walkthrough of the Fleet triage and Evidence pages.

## What was built, and in what order

The engineering came first: simulator, classifier, NIST validation, API, dashboard. Discovery did not happen before the build. The product work here reframes what exists around a user and a decision, adds the one feature that user needs (`api/routers/fleet.py`, `web/src/pages/FleetPage.tsx`), and writes down the discovery that should have come first. Done again, interviews would come before the first line of the simulator.
