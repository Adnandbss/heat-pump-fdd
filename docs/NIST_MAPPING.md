# NIST measurement → feature mapping

Working reference for confronting this project's simulated fault signatures with NIST
experimental data. Companion to the *External validation* section of
[ARCHITECTURE.md](ARCHITECTURE.md).

Row labels quoted below come from `data/nistir_7350_data_in_appendix_d(NF).csv`; NIST uses
the same instrumentation template across the campaign.

## Units

The simulator works in **bar, °C, K, W, kg/s** (verified on a nominal cycle:
`P_evap` 8.50 bar, `P_cond` 27.26 bar, `W_comp` 1449 W, `Q_cond` 3723 W). NIST tabulates in
US customary units.

| Quantity | NIST | Simulator | Conversion |
|---|---|---|---|
| Temperature | °F | °C | `(F − 32) × 5/9` |
| Temperature difference (superheat, subcooling, ΔT) | °F | K | `× 5/9` |
| Pressure | psia | bar | `× 0.0689476` |
| Capacity / heat rate | Btu/h | W | `× 0.293071` |
| Mass flow | lbm/h | kg/s | `× 1.2600 × 10⁻⁴` |
| Power | W | W | none |

## Feature mapping

`FEATURE_COLUMNS` in `src/fdd/features.py`, in order.

| # | Feature | NIST source | Status |
|---|---|---|---|
| 1 | `T_ambient` | Outdoor Dry-Bulb Temperature | direct |
| 2 | `T_setpoint` | Indoor Dry-Bulb Temperature | direct — **but see sink caveat** |
| 3 | `compressor_speed_ratio` | — | ❌ **not measurable**: single-speed unit |
| 4 | `P_evap` | Compressor Suction Pressure *(or Evaporator Exit Pressure)* | direct |
| 5 | `P_cond` | Compressor Discharge Pressure *(or Condenser Inlet Pressure)* | direct |
| 6 | `T_evap` | Evaporator Exit Sat. Temperature | direct |
| 7 | `T_cond` | Condenser Inlet Sat. Temperature | direct |
| 8 | `T_suction` | Compressor Suction Temperature | direct |
| 9 | `T_discharge` | Compressor Discharge Temperature | direct |
| 10 | `superheat` | Evaporator Exit Superheat | direct |
| 11 | `subcooling` | Condenser Exit Subcooling | direct |
| 12 | `compression_ratio` | — | derived: `P_cond / P_evap` |
| 13 | `W_comp` | Comp Power Consumption (W) | direct, no conversion |
| 14 | `Q_cond` | Condenser Capacity (Btu/h) | direct |
| 15 | `COP` | — | derived: `Q_cond / W_comp` |
| 16 | `delta_T_evap` | — | derived: `T_ambient − T_evap` |
| 17 | `delta_T_cond` | — | derived: `T_cond − T_setpoint` |
| 18 | `pressure_ratio` | — | derived — **duplicate of #12, see below** |
| 19 | `capacity_ratio` | — | derived: `Q_cond / 10000`; the 10 kW nominal is this project's machine, not NIST's |
| 20 | `d_T_discharge` | faulted − no-fault, same test condition | via `baseline=` |
| 21 | `d_superheat` | idem | via `baseline=` |
| 22 | `d_subcooling` | idem | via `baseline=` |
| 23 | `d_COP` | idem | via `baseline=` |
| 24 | `d_W_comp` | idem | via `baseline=` |

**23 of 24 features are recoverable.** Only `compressor_speed_ratio` has no counterpart: the
NIST units are single-speed, so it is constant. Since the model was trained over
`speed_ratio ∈ (0.3, 1.0)`, any NIST comparison sits at one edge of that domain.

### The five residuals need no code change

`cycle_to_features(..., baseline=...)` already accepts an external healthy cycle
(`src/features.py:86`). Passing a **measured** no-fault cycle as `baseline` and a
**measured** faulted cycle as `result` makes `d_*` real residuals. This is the seam that
makes the whole exercise additive — no pipeline module is modified.

NIST defines its residuals identically: *the fault-imposed value minus the fault-free value
at the same test condition*.

### `compression_ratio` and `pressure_ratio` are the same number

Verified identical to machine precision across operating points and fault types:

```
(7, 40, 0.7) nominal         3.206405  3.206405
(-5, 50, 1.0)                5.992225  5.992225
(7, 40, 0.7) fouling 0.40    3.313751  3.313751
(7, 40, 0.7) charge 0.80     3.523522  3.523522
```

`CycleResults.compression_ratio` is already `P_cond / P_evap`, which feature #18 recomputes.
The model therefore has **23 independent inputs, not 24**. Worth resolving during cleanup —
and the `test_feature_count` assertion pins 24, so it changes with it.

## Fault taxonomy

Two NIST datasets, two different answers. Which one you use decides what is possible.

### TN 1648 (heating, slopes only)

| NIST fault | Simulator parameter | Usable? |
|---|---|---|
| Indoor coil improper airflow | `fan_cond_ratio` *(heating: indoor coil **is** the condenser)* | ✅ |
| Outdoor coil improper airflow | `fan_evap_ratio` | ✅ |
| Refrigerant undercharge | `refrigerant_charge < 1.0` | ✅ |
| Refrigerant overcharge | `refrigerant_charge > 1.0` | ⚠️ only the undercharge branch is implemented |
| Compressor / four-way valve leakage | — | ❌ not modelled |
| Liquid line restriction | — | ❌ not modelled |
| — | `condenser_fouling`, `evaporator_fouling` | ❌ no counterpart |

Here airflow faults are imposed **by lowering fan speed**, so they map to `fan_*_ratio`, not
to `*_fouling`.

### 14 & 16 SEER campaign (cooling, raw rows)

`fdd_heat_pump_cooling_1416seer_longshort_alldata_2019.xlsx` — **7375 rows × 98 columns**,
fully instrumented on both air and refrigerant sides, with four fault-level columns.

| NIST column | Meaning | Closest project class |
|---|---|---|
| `NF` | fault-free flag | `Normal` |
| `CF` | outdoor coil **face area blockage**, % free | `Condenser_Fouling` |
| `EF` | indoor airflow level, % of nominal | `Evaporator_Fan_Fault` |
| `UC/OC` | charge level, % of nominal | `Refrigerant_Undercharge` / `_Overcharge` |
| `LL` | liquid line pressure drop | ❌ not modelled |

`CF` is physical **blockage of the condenser coil face**, not a fan speed change. That is far
closer to fouling than TN 1648's fan-driven fault, so `condenser_fouling` **does** have an
experimental counterpart here. `Evaporator_Fouling` and `Condenser_Fan_Fault` still do not.

In cooling mode the outdoor unit is the condenser and the indoor unit the evaporator — the
opposite of the heating-mode convention above. Check the mode before mapping anything.

## Row inventory (14 & 16 SEER)

Counting a fault as active when its level departs from nominal by more than 2 %:

| Class | Rows |
|---|---|
| No fault | 1353 |
| Undercharge | 1228 |
| Overcharge | 942 |
| Indoor airflow (`EF`) | 774 |
| Liquid line (`LL`) | 593 |
| Condenser blockage (`CF`) | 497 |
| **Single-fault + no-fault total** | **5387** |
| Simultaneous faults (2 at once) | 1988 |

Covariates: two machines (14 SEER 3289 rows / 16 SEER 4085) and two lineset lengths
(50 ft 3742 / long 3632). Training across both is a generalisation test, not a nuisance.

## Can the model be retrained on this data?

**Yes — on the 14 & 16 SEER campaign.** 5387 single-label measured rows across six classes,
balanced within a 2.7:1 ratio, is comparable in size to the 5000 synthetic rows and removes
the circularity entirely. The 1988 simultaneous-fault rows are a harder second problem the
synthetic pipeline cannot pose at all.

What it is not is the *same* project. Committing to it means accepting:

1. **Cooling mode, air-to-air.** The A7/W40 heating framing goes away. `T_sink` currently
   spans 30–55 °C, a water-side sink; this campaign delivers to indoor air near 21 °C.
2. **NIST's taxonomy.** Six classes: no-fault, condenser blockage, indoor airflow, liquid
   line, under- and overcharge. `Evaporator_Fouling` and `Condenser_Fan_Fault` disappear;
   liquid line restriction appears and is not modelled by the simulator.
3. **A lower headline number**, replacing 99.8 % with an honest one.
4. **Feature rework.** The 98 measured columns must be mapped and converted; `cycle_to_features`
   takes a `CycleResults`, so it needs an adapter or a parallel entry point.

The simulator is not wasted in that scenario — it moves to the role it already names in
`features.py`: the **no-fault reference model** of the Li & Braun residual method, with the
faulted side supplied by measurement instead of by itself.

TN 1648 remains the right source for heating-mode confrontation, and stays slope-only.
