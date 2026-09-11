import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchAshrae,
  fetchCondenserSweep,
  fetchCopCurves,
  fetchEvaporatorSweep,
  fetchPh,
  type PhPayload,
  type SweepPayload,
} from "../api";
import { tooltipStyle } from "../lib";
import { CycleSchematic } from "../components/CycleSchematic";
import { CycleShift } from "../components/CycleShift";
import { GlassCard } from "../components/GlassCard";
import { SelectField, SliderField } from "../components/Fields";

const TABS = ["P-h", "Schematic", "Load", "ASHRAE"] as const;
const LOAD_TABS = ["Sweeps", "Envelope", "P-h shift"] as const;

const IMPACT_ROWS = [
  { parameter: "T_cond", condenser: "↑↑ (+10–15 °C)", evaporator: "≈ (constant)" },
  { parameter: "T_evap", condenser: "≈ (constant)", evaporator: "↓↓ (−15–20 °C)" },
  { parameter: "P_cond", condenser: "↑ (+20–30%)", evaporator: "≈" },
  { parameter: "P_evap", condenser: "≈", evaporator: "↓↓ (−40–50%)" },
  { parameter: "τ (compression)", condenser: "↑ (+15–25%)", evaporator: "↑↑ (+50–100%)" },
  { parameter: "W_comp", condenser: "↑ (+10–20%)", evaporator: "↑ (+5–15%)" },
  { parameter: "Capacity Q", condenser: "↓ (−5–10%)", evaporator: "↓↓ (−30–50%)" },
  { parameter: "COP", condenser: "↓ (−15–25%)", evaporator: "↓↓ (−40–60%)" },
  { parameter: "MAIN IMPACT", condenser: "POWER UP", evaporator: "CAPACITY DOWN" },
] as const;

export function ThermoPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("P-h");
  const [loadTab, setLoadTab] = useState<(typeof LOAD_TABS)[number]>("Sweeps");
  const [tEvap, setTEvap] = useState(5);
  const [tCond, setTCond] = useState(45);
  const [superheat, setSuperheat] = useState(6);
  const [subcooling, setSubcooling] = useState(5);
  const [fault, setFault] = useState("Normal");
  const [ph, setPh] = useState<PhPayload>();
  const [cop, setCop] = useState<Awaited<ReturnType<typeof fetchCopCurves>>>();
  const [condSweep, setCondSweep] = useState<SweepPayload>();
  const [evapSweep, setEvapSweep] = useState<SweepPayload>();
  const [loadEvap, setLoadEvap] = useState(0);
  const [loadMin, setLoadMin] = useState(30);
  const [loadMax, setLoadMax] = useState(100);
  const [fixedCond, setFixedCond] = useState(45);
  const [sourceMin, setSourceMin] = useState(-15);
  const [sourceMax, setSourceMax] = useState(7);
  const [ashrae, setAshrae] = useState<Awaited<ReturnType<typeof fetchAshrae>>>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    fetchCopCurves()
      .then(setCop)
      .catch((err: Error) => setError(err.message));
    fetchAshrae()
      .then(setAshrae)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      fetchPh({ T_evap: tEvap, T_cond: tCond, superheat, subcooling })
        .then(setPh)
        .catch((err: Error) => setError(err.message));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [tEvap, tCond, superheat, subcooling]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      fetchCondenserSweep(loadEvap, loadMin, loadMax)
        .then(setCondSweep)
        .catch((err: Error) => setError(err.message));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [loadEvap, loadMin, loadMax]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      fetchEvaporatorSweep(fixedCond, sourceMin, sourceMax)
        .then(setEvapSweep)
        .catch((err: Error) => setError(err.message));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [fixedCond, sourceMin, sourceMax]);

  const satLiquid = ph?.saturation.map((row) => ({ h: row.h_liq, P: row.P })) ?? [];
  const satVapor = ph?.saturation.map((row) => ({ h: row.h_vap, P: row.P })) ?? [];
  const envelopeStatus = useMemo(() => {
    const normal = tEvap >= -20 && tEvap <= 20 && tCond >= 25 && tCond <= 65;
    const extended = tEvap >= -30 && tEvap <= 25 && tCond >= 20 && tCond <= 70;
    if (normal) return { label: "Inside envelope", tone: "text-emerald-300" };
    if (extended) return { label: "Near limit", tone: "text-amber-300" };
    return { label: "Outside envelope", tone: "text-rose-300" };
  }, [tEvap, tCond]);

  const condPath = (condSweep?.points ?? []).map((row) => ({ T_evap: loadEvap, T_cond: row.T_cond }));
  const evapPath = (evapSweep?.points ?? []).map((row) => ({ T_evap: row.T_evap, T_cond: fixedCond }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setTab(name)}
            className={
              tab === name
                ? "px-4 py-2 rounded-full bg-white text-slate-900 text-sm font-semibold"
                : "px-4 py-2 rounded-full glass text-sm text-white/70"
            }
          >
            {name}
          </button>
        ))}
      </div>

      {error ? <GlassCard className="p-4 text-sm text-amber-200">{error}</GlassCard> : null}

      {tab === "P-h" ? (
        <>
          <GlassCard className="p-5">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <SliderField label="T_evap" value={tEvap} min={-15} max={15} step={0.5} suffix=" °C" onChange={setTEvap} />
              <SliderField label="T_cond" value={tCond} min={30} max={60} step={0.5} suffix=" °C" onChange={setTCond} />
              <SliderField label="Superheat" value={superheat} min={2} max={12} step={0.5} suffix=" K" onChange={setSuperheat} />
              <SliderField label="Subcooling" value={subcooling} min={2} max={10} step={0.5} suffix=" K" onChange={setSubcooling} />
            </div>
            <p className="text-xs text-white/40 mt-3">
              {ph?.coolprop ? "CoolProp R410A saturation" : "Approximate saturation"} · COP{" "}
              {ph ? ph.COP.toFixed(2) : "—"} · P_evap {ph ? ph.P_evap.toFixed(2) : "—"} bar · P_cond{" "}
              {ph ? ph.P_cond.toFixed(2) : "—"} bar · {envelopeStatus.label}
            </p>
          </GlassCard>
          <GlassCard className="p-6">
            <h2 className="text-lg font-semibold mb-1">P-h diagram</h2>
            <p className="text-xs text-white/45 mb-4">1→2 compression · 2→3 condensation · 3→4 expansion · 4→1 evaporation</p>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="h" type="number" domain={[150, 500]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <YAxis dataKey="P" type="number" scale="log" domain={[2, 50]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Line data={satLiquid} dataKey="P" name="Saturated liquid" stroke="#94A3B8" dot={false} />
                  <Line data={satVapor} dataKey="P" name="Saturated vapor" stroke="#CBD5E1" dot={false} />
                  <Line data={ph?.cycle ?? []} dataKey="P" name="Cycle" stroke="#5B9DFF" strokeWidth={3} dot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <GlassCard className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">Compressor envelope</h2>
                <span className={`text-sm ${envelopeStatus.tone}`}>{envelopeStatus.label}</span>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                    <XAxis type="number" dataKey="T_evap" domain={[-35, 30]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                    <YAxis type="number" dataKey="T_cond" domain={[15, 75]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Scatter data={[{ T_evap: tEvap, T_cond: tCond }]} fill="#5B9DFF" name="Operating point" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
            <GlassCard className="p-6">
              <h2 className="text-lg font-semibold mb-4">COP vs ambient</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={cop?.curves ?? []}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="T_amb" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                    <YAxis tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend />
                    <Line dataKey="carnot" name="Carnot" stroke="#94A3B8" strokeDasharray="4 4" dot={false} />
                    <Line dataKey="estimated" name="Estimated" stroke="#7DFF7A" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </GlassCard>
          </div>
        </>
      ) : null}

      {tab === "Schematic" ? (
        <GlassCard className="p-6">
          <h2 className="text-lg font-semibold mb-4">System schematic</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <SliderField label="T_evap" value={tEvap} min={-10} max={15} step={0.5} suffix=" °C" onChange={setTEvap} />
            <SliderField label="T_cond" value={tCond} min={30} max={60} step={0.5} suffix=" °C" onChange={setTCond} />
            <SliderField label="Superheat" value={superheat} min={2} max={15} step={0.5} suffix=" K" onChange={setSuperheat} />
            <SelectField
              label="Simulated state"
              value={fault}
              options={[
                "Normal",
                "Condenser_Fouling",
                "Evaporator_Fouling",
                "Refrigerant_Undercharge",
                "Condenser_Fan_Fault",
              ].map((name) => ({ value: name, label: name.replace(/_/g, " ") }))}
              onChange={setFault}
            />
          </div>
          <CycleSchematic
            T_evap={tEvap}
            T_cond={tCond}
            P_evap={ph?.P_evap ?? 8}
            P_cond={ph?.P_cond ?? 24}
            superheat={superheat}
            subcooling={subcooling}
            COP={ph?.COP ?? 0}
            fault={fault}
          />
        </GlassCard>
      ) : null}

      {tab === "Load" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {LOAD_TABS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setLoadTab(name)}
                className={
                  loadTab === name
                    ? "px-3 py-1.5 rounded-full bg-white/90 text-slate-900 text-xs font-semibold"
                    : "px-3 py-1.5 rounded-full glass text-xs text-white/70"
                }
              >
                {name}
              </button>
            ))}
          </div>

          {loadTab === "Sweeps" ? (
            <>
          <GlassCard className="p-5">
            <h2 className="text-lg font-semibold mb-1">Condenser load down</h2>
            <p className="text-xs text-white/45 mb-4">Heating demand drops · T_cond rises as load falls</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <SliderField label="Fixed T_evap" value={loadEvap} min={-10} max={10} step={1} suffix=" °C" digits={0} onChange={setLoadEvap} />
              <SliderField label="Load min" value={loadMin} min={20} max={90} step={5} suffix=" %" digits={0} onChange={setLoadMin} />
              <SliderField label="Load max" value={loadMax} min={40} max={100} step={5} suffix=" %" digits={0} onChange={setLoadMax} />
            </div>
            <DeltaPills deltas={condSweep?.deltas} />
            <SweepGrid
              data={condSweep}
              xKey="load"
              series={[
                { key: "COP", color: "#5B9DFF" },
                { key: "P_cond", color: "#F472B6" },
                { key: "W_comp", color: "#C4B5FD" },
                { key: "T_dis", color: "#FB923C" },
              ]}
            />
            <p className="text-sm text-amber-200 mt-4">{condSweep?.headline}</p>
          </GlassCard>

          <GlassCard className="p-5">
            <h2 className="text-lg font-semibold mb-1">Evaporator source down</h2>
            <p className="text-xs text-white/45 mb-4">Outdoor temperature drops · capacity collapses</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <SliderField label="Fixed T_cond" value={fixedCond} min={35} max={55} step={1} suffix=" °C" digits={0} onChange={setFixedCond} />
              <SliderField label="Source min" value={sourceMin} min={-20} max={5} step={1} suffix=" °C" digits={0} onChange={setSourceMin} />
              <SliderField label="Source max" value={sourceMax} min={-5} max={15} step={1} suffix=" °C" digits={0} onChange={setSourceMax} />
            </div>
            <DeltaPills deltas={evapSweep?.deltas} />
            <SweepGrid
              data={evapSweep}
              xKey="t_source"
              series={[
                { key: "COP", color: "#5B9DFF" },
                { key: "P_evap", color: "#7DFF7A" },
                { key: "tau", color: "#7EC8FF" },
                { key: "Q_evap", color: "#C4B5FD" },
              ]}
            />
            <p className="text-sm text-amber-200 mt-4">{evapSweep?.headline}</p>
          </GlassCard>
            </>
          ) : null}

          {loadTab === "Envelope" ? (
            <>
          <GlassCard className="p-6">
            <h2 className="text-lg font-semibold mb-4">Compressor envelope trajectories</h2>
              <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis type="number" dataKey="T_evap" domain={[-30, 20]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <YAxis type="number" dataKey="T_cond" domain={[20, 80]} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <ReferenceArea x1={-30} x2={25} y1={20} y2={70} fill="#FB923C" fillOpacity={0.06} />
                  <ReferenceArea x1={-20} x2={20} y1={25} y2={65} fill="#7DFF7A" fillOpacity={0.1} />
                  <Scatter name="Cond. load ↓" data={condPath} fill="#FB923C" line />
                  <Scatter name="Source ↓" data={evapPath} fill="#C4B5FD" line />
                  <Scatter name="Nominal" data={[{ T_evap: 0, T_cond: 45 }]} fill="#7DFF7A" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-white/50 mt-4">
              Condenser load mainly changes compressor power. Evaporator source mainly changes heating capacity.
              COP falls in both cases and the point walks toward envelope limits.
            </p>
          </GlassCard>

          <GlassCard className="p-6">
            <h2 className="text-lg font-semibold mb-1">Impact comparison</h2>
            <p className="text-xs text-white/45 mb-4">Condenser load vs evaporator source — same physics as the lab sweeps</p>
            <table className="w-full text-sm">
              <thead className="text-white/40 text-xs">
                <tr>
                  <th className="text-left font-medium pb-2 pr-3">Parameter</th>
                  <th className="text-left font-medium pb-2 pr-3">Cond. load down</th>
                  <th className="text-left font-medium pb-2">Evap. source down</th>
                </tr>
              </thead>
              <tbody>
                {IMPACT_ROWS.map((row) => (
                  <tr key={row.parameter} className="border-t border-white/8">
                    <td className={`py-2 pr-3 ${row.parameter === "MAIN IMPACT" ? "font-semibold text-amber-200" : ""}`}>
                      {row.parameter}
                    </td>
                    <td className={`py-2 pr-3 ${row.parameter === "MAIN IMPACT" ? "font-semibold text-amber-200" : "text-white/80"}`}>
                      {row.condenser}
                    </td>
                    <td className={`py-2 ${row.parameter === "MAIN IMPACT" ? "font-semibold text-amber-200" : "text-white/80"}`}>
                      {row.evaporator}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
            </>
          ) : null}

          {loadTab === "P-h shift" ? <CycleShift /> : null}
        </div>
      ) : null}

      {tab === "ASHRAE" ? (
        <GlassCard className="p-6">
          <h2 className="text-lg font-semibold mb-1">R410A saturation check</h2>
          <p className="text-xs text-white/45 mb-4">
            {ashrae?.coolprop ? "CoolProp vs ASHRAE handbook values" : "CoolProp offline — approximate correlations"}
          </p>
          <table className="w-full text-sm">
            <thead className="text-white/40 text-xs">
              <tr>
                {["T (°C)", "ASHRAE bar", "CoolProp bar", "Error %"].map((col) => (
                  <th key={col} className="text-left font-medium pb-2 pr-3">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(ashrae?.rows ?? []).map((row) => (
                <tr key={row.T} className="border-t border-white/8">
                  <td className="py-2 pr-3">{row.T}</td>
                  <td className="py-2 pr-3">{row.ashrae.toFixed(2)}</td>
                  <td className="py-2 pr-3">{row.coolprop.toFixed(2)}</td>
                  <td className={row.error_pct < 1.5 ? "py-2 pr-3 text-emerald-300" : "py-2 pr-3 text-amber-200"}>
                    {row.error_pct.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      ) : null}
    </div>
  );
}

function DeltaPills({ deltas }: { deltas?: Record<string, number> }) {
  if (!deltas) return null;
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {Object.entries(deltas).map(([key, value]) => (
        <span key={key} className="glass-pill text-xs px-3 py-1 tabular-nums">
          Δ {key} {value >= 0 ? "+" : ""}
          {value.toFixed(1)}%
        </span>
      ))}
    </div>
  );
}

function SweepGrid({
  data,
  xKey,
  series,
}: {
  data?: SweepPayload;
  xKey: "load" | "t_source";
  series: Array<{ key: "COP" | "P_cond" | "P_evap" | "W_comp" | "T_dis" | "tau" | "Q_evap"; color: string }>;
}) {
  const rows = data?.points ?? [];
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {series.map((item) => (
        <div key={item.key} className="h-40">
          <p className="text-xs text-white/45 mb-1">{item.key}</p>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <XAxis dataKey={xKey} tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }} width={36} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey={item.key} stroke={item.color} dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}
