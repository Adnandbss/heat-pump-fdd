import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { postLive, type ActivityPoint } from "../api";
import { pretty, tooltipStyle } from "../lib";
import { GlassCard } from "../components/GlassCard";
import { SelectField, SliderField } from "../components/Fields";

const FAULTS = [
  "Condenser_Fouling",
  "Evaporator_Fouling",
  "Refrigerant_Undercharge",
  "Condenser_Fan_Fault",
  "Evaporator_Fan_Fault",
  "Normal",
];

export function LivePage() {
  const [fault, setFault] = useState("Condenser_Fouling");
  const [injectAt, setInjectAt] = useState(20);
  const [nPoints, setNPoints] = useState(55);
  const [trace, setTrace] = useState<ActivityPoint[]>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  function run(nextFault = fault, nextInject = injectAt, nextN = nPoints) {
    setLoading(true);
    setError(undefined);
    postLive({ fault_type: nextFault, inject_at: nextInject, n_points: nextN })
      .then((payload) => setTrace(payload.trace))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    run();
    // initial live trace only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const last = trace?.[trace.length - 1];
  const tail = useMemo(() => (trace ?? []).slice(-12).reverse(), [trace]);

  const charts = [
    { key: "P_cond", color: "#8B5CF6", label: "P_cond (bar)" },
    { key: "P_evap", color: "#2DD4BF", label: "P_evap (bar)" },
    { key: "COP", color: "#34F5A6", label: "COP" },
    { key: "confidence", color: "#A78BFA", label: "Confidence" },
  ] as const;

  return (
    <div className="space-y-4">
      <GlassCard className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <SelectField
            label="Fault to inject"
            value={fault}
            options={FAULTS.map((name) => ({ value: name, label: pretty(name) }))}
            onChange={setFault}
          />
          <SliderField
            label="Injection timestep"
            value={injectAt}
            min={5}
            max={45}
            step={1}
            onChange={setInjectAt}
          />
          <SliderField
            label="Duration"
            value={nPoints}
            min={20}
            max={80}
            step={1}
            onChange={setNPoints}
          />
          <button
            type="button"
            onClick={() => run()}
            disabled={loading}
            className="rounded-2xl bg-gradient-to-r from-violet-500 to-indigo-500 px-4 py-3 text-sm font-semibold disabled:opacity-50"
          >
            {loading ? "Running…" : "Inject & diagnose"}
          </button>
        </div>
        <p className="text-xs text-white/40 mt-3">
          Each timestep is a CoolProp cycle + calibrated Gradient Boosting prediction. The magenta
          line is the injection.
        </p>
      </GlassCard>

      {error ? <GlassCard className="p-4 text-sm text-amber-200">{error}</GlassCard> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {charts.map((chart) => (
          <GlassCard key={chart.key} className="p-5">
            <h3 className="text-sm font-medium mb-3">{chart.label}</h3>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trace ?? []}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} width={42} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine x={injectAt} stroke="#F472B6" strokeDasharray="4 4" />
                  <Line
                    type="monotone"
                    dataKey={chart.key}
                    stroke={chart.color}
                    dot={false}
                    strokeWidth={2.2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <GlassCard className="p-6">
          <p className="text-xs uppercase tracking-wide text-white/45">Latest prediction</p>
          <div className="text-2xl font-semibold mt-3">{last ? pretty(last.predicted) : "—"}</div>
          <p className="text-sm text-white/50 mt-1">
            {last ? `${(last.confidence * 100).toFixed(0)}% confidence` : "run a trace"}
          </p>
        </GlassCard>
        <GlassCard className="p-6 xl:col-span-2 overflow-x-auto">
          <h3 className="text-sm font-medium mb-3">Last 12 timesteps</h3>
          <table className="w-full text-xs">
            <thead className="text-white/40">
              <tr>
                {["t", "predicted", "conf", "P_cond", "COP"].map((col) => (
                  <th key={col} className="text-left font-medium pb-2 pr-3">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tail.map((row) => (
                <tr key={row.t} className="border-t border-white/8">
                  <td className="py-1.5 pr-3">{row.t}</td>
                  <td className="py-1.5 pr-3">{pretty(row.predicted)}</td>
                  <td className="py-1.5 pr-3">{(row.confidence * 100).toFixed(0)}%</td>
                  <td className="py-1.5 pr-3">{row.P_cond.toFixed(2)}</td>
                  <td className="py-1.5 pr-3">{row.COP.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      </div>
    </div>
  );
}
