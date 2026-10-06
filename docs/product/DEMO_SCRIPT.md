# Demo script — two minutes

> **Status:** Plan — the script for the walkthrough video. Not recorded yet.

Before recording: open the deployed API URL once and wait for it to answer. The free hosting tier sleeps when idle, and the first request can take about a minute.

| Time | Screen | Say |
|---|---|---|
| 0:00 | Fleet triage page, top | "A heat-pump manufacturer can see its connected units. The faults that cost the most — a slow refrigerant leak, a fouled exchanger — don't raise a fault code. This is the service queue its after-sales team would open in the morning." |
| 0:20 | Summary cards | "Each unit gets one action: dispatch, engineering review, monitor, or nothing. And this card counts the dispatches the evidence gate held back." |
| 0:35 | First dispatched rows, instruction column | "These are charge faults. They get dispatched, with an instruction for the installer: leak search and recharge." |
| 0:50 | Hover an evidence badge | "Every row shows why it is trusted. This badge reads the logged result: a classifier trained on the simulator still finds charge faults on real NIST test units." |
| 1:05 | An engineering-review row, then toggle ground truth | "This fault does not transfer to real machines, so it goes to engineering review instead of a truck roll. With the simulated ground truth on, you can see the case the gate protects: a unit misread as condenser fouling." |
| 1:25 | Evidence page, the ladder | "The gate comes from here. Same model, different protocols: 89 percent on simulated data, much lower on real machines. The product only promises what the bottom of this ladder supports." |
| 1:45 | Case study page on GitHub | "What I'd do differently: interviews before the simulator. The research kit is ready, and it's the next step." |
| 2:00 | End | |

Keep the numbers on screen rather than in the voice-over, except the one the ladder shows. They come from `outputs/results.csv` and can change.
