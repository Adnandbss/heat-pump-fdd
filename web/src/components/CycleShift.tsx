import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchPhCompare, type PhComparePayload, type PhOverlay } from "../api";
import { tooltipStyle } from "../lib";
import { GlassCard } from "./GlassCard";
import { SliderField } from "./Fields";

const SCENARIOS = [
  { id: "all", label: "Compare all three" },
  { id: "nominal", label: "Nominal" },
  { id: "condenser", label: "Cond. load down" },
  { id: "evaporator", label: "Source down" },
] as const;

type Scenario = (typeof SCENARIOS)[number]["id"];

export function CycleShift() {
  const [scenario, setScenario] = useState<Scenario>("all");
  const [tEvap, setTEvap] = useState(0);
  const [tCond, setTCond] = useState(45);
  const [superheat, setSuperheat] = useState(8);
  const [subcooling, setSubcooling] = useState(5);
  const [loadFactor, setLoadFactor] = useState(50);
  const [tSource, setTSource] = useState(-10);
  const [data, setData] = useState<PhComparePayload>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const handle = window.setTimeout(() => {
      fetchPhCompare({
        T_evap: tEvap,
        T_cond: tCond,
        superheat,
        subcooling,
        load_factor: loadFactor,
        t_source: tSource,
        scenario,
      })
        .then(setData)
        .catch((err: Error) => setError(err.message));
    }, 220);
    return () => window.clearTimeout(handle);
  }, [scenario, tEvap, tCond, superheat, subcooling, loadFactor, tSource]);

  const satLiquid = data?.saturation.map((row) => ({ h: row.h_liq, P: row.P })) ?? [];
  const satVapor = data?.saturation.map((row) => ({ h: row.h_vap, P: row.P })) ?? [];
  const showLoad = scenario === "condenser" || scenario === "all";
  const showSource = scenario === "evaporator" || scenario === "all";

  return (
    <GlassCard className="p-5">
      <h2 className="text-lg font-semibold mb-1">Cycle shift on the P-h diagram</h2>
      <p className="text-xs text-white/45 mb-4">
        Watch the vapour-compression loop move when condenser load or outdoor source changes
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {SCENARIOS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setScenario(item.id)}
            className={
              scenario === item.id
                ? "px-3 py-1.5 rounded-full bg-white text-slate-900 text-xs font-semibold"
                : "px-3 py-1.5 rounded-full glass text-xs text-white/70"
            }
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <SliderField label="Nominal T_evap" value={tEvap} min={-10} max={10} step={1} suffix=" °C" digits={0} onChange={setTEvap} />
        <SliderField label="Nominal T_cond" value={tCond} min={35} max={55} step={1} suffix=" °C" digits={0} onChange={setTCond} />
        <SliderField label="Superheat" value={superheat} min={2} max={15} step={0.5} suffix=" K" onChange={setSuperheat} />
        <SliderField label="Subcooling" value={subcooling} min={2} max={12} step={0.5} suffix=" K" onChange={setSubcooling} />
        {showLoad ? (
          <SliderField label="Condenser load" value={loadFactor} min={30} max={100} step={5} suffix=" %" digits={0} onChange={setLoadFactor} />
        ) : null}
        {showSource ? (
          <SliderField label="Outdoor source" value={tSource} min={-15} max={15} step={1} suffix=" °C" digits={0} onChange={setTSource} />
        ) : null}
      </div>

      {error ? <p className="text-sm text-amber-200 mb-3">{error}</p> : null}

      <div className="h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis
              dataKey="h"
              type="number"
              domain={[150, 500]}
              tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }}
            />
            <YAxis
              dataKey="P"
              type="number"
              scale="log"
              domain={[3, 50]}
              tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }}
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend />
            <Line data={satLiquid} dataKey="P" name="Saturated liquid" stroke="#94A3B8" strokeDasharray="4 4" dot={false} />
            <Line data={satVapor} dataKey="P" name="Saturated vapour" stroke="#CBD5E1" strokeDasharray="4 4" dot={false} />
            <Line
              data={data?.nominal.cycle ?? []}
              dataKey="P"
              name="Nominal"
              stroke="#7DFF7A"
              strokeWidth={3}
              dot={{ r: 5 }}
            />
            {data?.condenser ? (
              <Line
                data={data.condenser.cycle}
                dataKey="P"
                name="Cond. load ↓"
                stroke="#FB923C"
                strokeWidth={3}
                strokeDasharray="6 4"
                dot={{ r: 5 }}
              />
            ) : null}
            {data?.evaporator ? (
              <Line
                data={data.evaporator.cycle}
                dataKey="P"
                name="Source ↓"
                stroke="#C4B5FD"
                strokeWidth={3}
                strokeDasharray="2 3"
                dot={{ r: 5 }}
              />
            ) : null}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
        {data ? <OverlayStats title="Nominal" tone="text-emerald-300" overlay={data.nominal} /> : null}
        {data?.condenser ? (
          <OverlayStats title="Cond. load ↓" tone="text-orange-300" overlay={data.condenser} />
        ) : null}
        {data?.evaporator ? (
          <OverlayStats title="Source ↓" tone="text-violet-300" overlay={data.evaporator} />
        ) : null}
      </div>

      <ShiftCopy scenario={scenario} data={data} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-xs text-white/50">
        <p>
          <span className="text-white/70">Cycle points:</span> 1 evaporator outlet · 2 compressor
          discharge · 3 condenser outlet · 4 expansion outlet
        </p>
        <p>
          <span className="text-white/70">Transforms:</span> 1→2 compression · 2→3 condensation · 3→4
          isenthalpic expansion · 4→1 evaporation
        </p>
      </div>
    </GlassCard>
  );
}

function OverlayStats({
  title,
  tone,
  overlay,
}: {
  title: string;
  tone: string;
  overlay: PhOverlay;
}) {
  return (
    <div className="glass p-3 text-sm">
      <div className={`text-xs uppercase tracking-wide mb-2 ${tone}`}>{title}</div>
      <div className="tabular-nums space-y-1 text-white/80">
        <div>
          T {overlay.T_evap.toFixed(1)} / {overlay.T_cond.toFixed(1)} °C
        </div>
        <div>
          P {overlay.P_evap.toFixed(2)} / {overlay.P_cond.toFixed(2)} bar
        </div>
        <div>COP {overlay.COP.toFixed(2)}</div>
      </div>
    </div>
  );
}

function ShiftCopy({ scenario, data }: { scenario: Scenario; data?: PhComparePayload }) {
  if (!data) return null;
  if (scenario === "condenser" && data.condenser) {
    const dP = data.condenser.P_cond - data.nominal.P_cond;
    return (
      <p className="text-sm text-white/70 mt-4">
        Reduced condenser load: P_cond rises by <span className="text-orange-300">{dP.toFixed(2)} bar</span>{" "}
        — the cycle moves up and widens. Electrical consumption goes up.
      </p>
    );
  }
  if (scenario === "evaporator" && data.evaporator) {
    const dP = data.evaporator.P_evap - data.nominal.P_evap;
    return (
      <p className="text-sm text-white/70 mt-4">
        Colder source: P_evap falls by <span className="text-violet-300">{Math.abs(dP).toFixed(2)} bar</span>{" "}
        — the cycle moves down and shrinks. Heating capacity goes down.
      </p>
    );
  }
  if (scenario === "all") {
    return (
      <p className="text-sm text-white/70 mt-4">
        Green is the efficient reference. Orange (condenser load down) climbs in P_cond and costs more
        compressor work. Purple (colder source) drops P_evap and cuts capacity. Both hurt COP, for
        different physical reasons.
      </p>
    );
  }
  return (
    <p className="text-sm text-white/70 mt-4">
      Nominal cycle at the chosen evaporation and condensation temperatures.
    </p>
  );
}
