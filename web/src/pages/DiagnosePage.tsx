import { useEffect, useState } from "react";
import {
  fetchCatalog,
  postPredict,
  postSimulate,
  type Catalog,
  type Diagnosis,
} from "../api";
import { pretty } from "../lib";
import { GlassCard } from "../components/GlassCard";
import { ProbabilityBars } from "../components/ProbabilityBars";
import { SelectField, SliderField } from "../components/Fields";

export function DiagnosePage() {
  const [catalog, setCatalog] = useState<Catalog>();
  const [scenario, setScenario] = useState("Condenser fouling 40%");
  const [tSource, setTSource] = useState(7);
  const [tSink, setTSink] = useState(40);
  const [speed, setSpeed] = useState(70);
  const [payload, setPayload] = useState<Diagnosis>();
  const [manual, setManual] = useState<Record<string, number>>();
  const [manualResult, setManualResult] = useState<Diagnosis["diagnosis"]>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [showManual, setShowManual] = useState(false);

  const spec = catalog?.scenarios.find((row) => row.title === scenario);

  useEffect(() => {
    fetchCatalog()
      .then((next) => {
        setCatalog(next);
        if (next.scenarios[0]) setScenario(next.scenarios[1]?.title ?? next.scenarios[0].title);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!catalog) return;
    const current = catalog.scenarios.find((row) => row.title === scenario);
    if (!current) return;
    const handle = window.setTimeout(() => {
      setLoading(true);
      postSimulate({
        T_source: tSource,
        T_sink: tSink,
        speed_ratio: speed / 100,
        fault_type: current.fault_type,
      })
        .then((next) => {
          setPayload(next);
          setManual(next.features);
          setManualResult(undefined);
        })
        .catch((err: Error) => setError(err.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [catalog, scenario, tSource, tSink, speed]);

  const diagnosis = payload?.diagnosis;
  const cycle = payload?.cycle;
  const healthy = diagnosis?.label === "Normal";

  return (
    <div className="space-y-4">
      <GlassCard className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <SelectField
            label="Preset scenario"
            value={scenario}
            options={(catalog?.scenarios ?? []).map((row) => ({
              value: row.title,
              label: row.title,
            }))}
            onChange={setScenario}
          />
          <SliderField
            label="Source temperature"
            value={tSource}
            min={-10}
            max={20}
            step={0.5}
            suffix=" °C"
            onChange={setTSource}
          />
          <SliderField
            label="Sink temperature"
            value={tSink}
            min={30}
            max={55}
            step={0.5}
            suffix=" °C"
            onChange={setTSink}
          />
          <SliderField
            label="Compressor speed"
            value={speed}
            min={30}
            max={100}
            step={1}
            suffix=" %"
            digits={0}
            onChange={setSpeed}
          />
        </div>
        <p className="text-xs text-white/40 mt-3">
          {spec?.description ?? "Pick a scenario"} · {loading ? "updating…" : "inference via API"}
        </p>
      </GlassCard>

      {error ? <GlassCard className="p-4 text-sm text-amber-200">{error}</GlassCard> : null}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <GlassCard className="p-6 xl:col-span-4">
          <p className="text-xs uppercase tracking-wide text-white/45">Diagnosis</p>
          <div className={`text-3xl font-semibold mt-4 ${healthy ? "text-emerald-300" : "text-violet-200"}`}>
            {diagnosis ? pretty(diagnosis.label) : "—"}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-6">
            <Metric label="Confidence" value={diagnosis ? `${(diagnosis.confidence * 100).toFixed(1)}%` : "—"} />
            <Metric label="COP" value={cycle ? cycle.COP.toFixed(2) : "—"} />
            <Metric label="T_dis" value={cycle ? `${cycle.T_discharge.toFixed(1)}°` : "—"} />
          </div>
        </GlassCard>
        <GlassCard className="p-6 xl:col-span-8">
          <h2 className="text-sm font-semibold mb-4">Class probabilities</h2>
          <ProbabilityBars payload={payload} />
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <MetricCard label="P_evap" value={cycle ? `${cycle.P_evap.toFixed(2)} bar` : "—"} />
        <MetricCard label="P_cond" value={cycle ? `${cycle.P_cond.toFixed(2)} bar` : "—"} />
        <MetricCard label="Superheat" value={cycle ? `${cycle.superheat.toFixed(1)} K` : "—"} />
        <MetricCard label="Subcooling" value={cycle ? `${cycle.subcooling.toFixed(1)} K` : "—"} />
      </div>

      <GlassCard className="p-6">
        <button
          type="button"
          className="text-sm text-white/70 hover:text-white"
          onClick={() => setShowManual((open) => !open)}
        >
          {showManual ? "Hide" : "Show"} manual feature vector
        </button>
        {showManual && manual ? (
          <div className="mt-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.entries(manual).map(([name, value]) => (
                <label key={name} className="text-xs">
                  <span className="text-white/45">{name}</span>
                  <input
                    type="number"
                    step="0.0001"
                    value={value}
                    onChange={(event) =>
                      setManual((current) => ({
                        ...current,
                        [name]: Number(event.target.value),
                      }))
                    }
                    className="mt-1 w-full rounded-xl bg-white/8 border border-white/10 px-3 py-2 text-sm"
                  />
                </label>
              ))}
            </div>
            <button
              type="button"
              className="mt-4 rounded-2xl bg-gradient-to-r from-violet-500 to-indigo-500 px-4 py-2 text-sm font-semibold"
              onClick={() => {
                if (!manual) return;
                postPredict(manual)
                  .then(setManualResult)
                  .catch((err: Error) => setError(err.message));
              }}
            >
              Diagnose manual vector
            </button>
            {manualResult ? (
              <p className="text-sm mt-3 text-white/70">
                {pretty(manualResult.label)} · {(manualResult.confidence * 100).toFixed(1)}%
              </p>
            ) : null}
          </div>
        ) : null}
      </GlassCard>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-white/40">{label}</div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <GlassCard className="p-4">
      <div className="text-[11px] uppercase tracking-wide text-white/45">{label}</div>
      <div className="text-xl font-semibold mt-2">{value}</div>
    </GlassCard>
  );
}
