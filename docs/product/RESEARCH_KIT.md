# Research kit — interviews and usability test

> **Status:** Template — the instruments are ready; no session has been run. Results go in the synthesis grid at the end, and the assumptions in [DISCOVERY.md](DISCOVERY.md) are updated from it.

## Research questions

1. Which faults cost an OEM after-sales team the most, and how do they find out about them today? (A1, A2)
2. How is the decision to send an installer made, and what does a wrong one cost? (A3)
3. What would make an engineer trust an automated fault alert enough to act on it? (A4)
4. What is measured on a unit at commissioning, and what does the connected unit stream? (A6, A7)

## Recruiting

Target: five to eight interviews, then three to five usability sessions.

| Profile | Why | Where to find them |
|---|---|---|
| OEM after-sales or service engineer | Primary user, owns the dispatch decision | LinkedIn titles: after-sales engineer, service engineer, field service manager, at heat-pump manufacturers |
| OEM service or connectivity product manager | Knows what the installer tools already do | Same, plus speakers at heating trade events |
| Installer partner who services heat pumps | Secondary user, knows the cost of a visit | Local installers, installer forums, OEM certified-installer directories |

Screener: works on heat pumps or chillers in service or after-sales; has dispatched or performed at least one refrigerant-related visit in the last six months.

Message: *"I am building a fault-detection tool for heat-pump fleets and want to understand how service visits are decided. Thirty minutes, no sales, and I will share what I learn."*

## Interview guide (30 to 45 minutes)

1. **Context.** Your role, the fleet you look after, the tools you use every day.
2. **Last story.** Tell me about the last visit that turned out to be a refrigerant or fouling problem. How did it start? Who noticed? What happened at the visit?
3. **Today's signal.** What do the remote tools show you before a visit? What do you do with a fault code? What do you do when there is no code but the customer complains?
4. **The decision.** How do you decide a unit needs a visit? Who decides? What makes you wait?
5. **Cost.** What does a visit that finds nothing cost you? A leak found late?
6. **Trust.** Have you had alerts you stopped reading? Why? What would an alert need to show for you to act on it?
7. **Data.** What is recorded at commissioning? Which sensor readings can you see remotely?
8. **Close.** If you had one change to how soft faults are handled, what would it be? Who else should I talk to?

Rules: ask about past behaviour, not opinions about the product. Do not show the dashboard before question 6.

## Usability test on the Fleet page (20 minutes)

Setup: the deployed demo or `make dev`, Fleet triage page. Think-aloud. The facilitator does not explain the page.

| Task | Success when the participant… |
|---|---|
| T1. Which units would you send someone to today? | names the units marked Dispatch, without help |
| T2. Pick a unit marked Engineering review. Why is it not dispatched? | explains that its fault is not validated on measured units |
| T3. What would you tell the installer for a dispatched unit? | reads the instruction column |
| T4. How sure is the system about the first unit? | finds confidence and evidence, and says which one matters to them |
| T5. Would you act on an "Engineering review" row? What would you do? | describes a next step (or says the row is useless — also a result) |

Capture per task: success (yes, with help, no), time, and a 1-to-7 ease rating. After the session: *"What would you remove? What is missing?"*

## Synthesis grid

| Participant | Profile | Date | Key quote | A1 | A2 | A3 | A4 | A5 | A6 | A7 | Usability issues |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | | | | | | | | | | | |
| P2 | | | | | | | | | | | |
| P3 | | | | | | | | | | | |
| P4 | | | | | | | | | | | |
| P5 | | | | | | | | | | | |

Mark each assumption cell `supports`, `contradicts` or `no signal`. An assumption moves to *Validated* in [DISCOVERY.md](DISCOVERY.md) only with support from at least three participants and no strong contradiction.

## Consent

Ask before recording. Notes are anonymised (P1, P2…). Company names are not written in the repository.
