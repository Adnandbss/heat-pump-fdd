# Market — who already does part of this

> **Status:** Desk research — public product pages read on 2026-10-06. Nothing here was checked with the vendors or tried hands-on.

## Category 1 — OEM installer remote-monitoring tools

The manufacturers already give installers a remote view of connected units. This is the tool our user opens every day, and the place where an alert would have to appear.

**Viessmann ViGuide.** A web and mobile service app for trade partners. Installers monitor their customers' online systems, see which systems have faults, and for each fault get a description of the cause and the action Viessmann recommends; it also covers commissioning of Vitocal heat pumps. The customer has to register the system in ViCare and grant remote access. Sources: [ViGuide (Viessmann UK)](https://www.viessmann.co.uk/en/products/control-system-and-connectivity/viguide-app.html), [ViGuide for contractors (Viessmann US)](https://www.viessmann-us.com/en/services/viessmann-apps/viguide.html).

**Vaillant myVAILLANT Pro Service.** Remote monitoring of connected boilers and heat pumps through the myVAILLANT connect gateway: performance data, fault-code history, live fault notifications, a fault-code assistant and spare-part identification. Vaillant's installer page describes an advance warning before water pressure falls too low, and marks the heat-pump version of that feature as *in development*. Sources: [myVAILLANT Pro Service (installers)](https://professional.vaillant.co.uk/for-installers/myvaillant-pro-service/), [myVaillant Pro Service tool](https://www.myvaillantpro.co.uk/service/service-tools/myvaillant-pro-service).

**What the pages describe.** Both centre on fault codes raised by the unit's controller, their history, and guidance once a code exists. Neither page claims to detect a gradual soft fault such as slow refrigerant loss before a code fires. That is an observation about the pages, not about the products, and it is assumption A2 in [DISCOVERY.md](DISCOVERY.md).

## Category 2 — Building fault detection and diagnostics platforms

Analytics vendors run FDD on data pulled from building management systems, mostly in commercial buildings.

**Clockworks Analytics.** A gateway connects to the existing BMS and meters and sends thousands of points to the cloud every five minutes. The engine diagnoses performance issues, prioritises each on a 0-to-10 scale for energy, comfort and equipment reliability, and attaches possible causes or suggested actions. Sources: [Clockworks software](https://clockworksanalytics.com/software/), [Diagnostics module manual](https://clockworksanalytics.atlassian.net/wiki/spaces/ClockworksAnalyticsUM/pages/3519250434).

**SkyFoundry SkySpark.** An analytics platform built on Project Haystack tagging, with a rule engine and a library of built-in HVAC functions (simultaneous heating and cooling, economiser conflicts, short cycling). Results appear as timelines with frequency, duration and cost. Sources: [SkySpark product](https://skyfoundry.com/product), [built-in analytic functions](https://skyfoundry.com/file/48/SkySpark---Combining-Full-Programmability-and-Built-in-Analytic-Functions.pdf).

**What the pages describe.** Air-side and plant-level rules on building data, sold to building owners and service providers. The examples on these pages are dampers, valves, sensors and schedules, not the refrigerant cycle of a residential heat pump.

## Where this project would sit

| | OEM installer tools | Building FDD platforms | This project |
|---|---|---|---|
| Buyer | The OEM, for its installers | Building owners, service providers | The OEM after-sales team |
| Signal | Controller fault codes | BMS points, rules | Refrigerant-cycle residuals against a healthy reference |
| Fault type | Hard faults with a code | Air side, controls, scheduling | Soft faults in the refrigerant cycle |
| Trust device | Manufacturer guidance per code | Prioritisation and cost of each issue | The evidence gate: only faults validated on measured units dispatch |

The opening, if it exists, is a module that feeds the OEM's own installer tool rather than a new app for installers. That is a hypothesis to test in interviews (A2), not a market size.

## Not covered yet

Market size, pricing of these tools, and the OEMs that build soft-fault detection in-house. None of these can be answered from public pages with any confidence. The interviews are the first source.
