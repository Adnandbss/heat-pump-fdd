import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchAdvanced, fetchAmbientHeatmap, fetchEvidenceSummary, fetchModels, isAbortError, type EvidenceSummary, type ModelsPayload } from "../api";
import { pretty, tooltipStyle } from "../lib";
import { GlassCard } from "../components/GlassCard";
import { HeatMap } from "../components/HeatMap";
import { ProtocolBadge } from "../components/ProtocolBadge";

const METRICS = ["Accuracy", "Precision", "Recall", "F1 Score"] as const;

export function ModelsPage() {
  const [models, setModels] = useState<ModelsPayload>();
  const [evidence, setEvidence] = useState<EvidenceSummary>();
  const [corr, setCorr] = useState<{ labels: string[]; matrix: number[][] }>();
  const [ambient, setAmbient] = useState<{ x_labels: string[]; y_labels: string[]; matrix: number[][] }>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchModels(controller.signal),
      fetchAdvanced(controller.signal),
      fetchAmbientHeatmap(controller.signal),
      fetchEvidenceSummary(controller.signal).catch((err: Error) => {
        if (isAbortError(err)) throw err;
        return undefined;
      }),
    ])
      .then(([nextModels, nextCorr, nextAmbient, nextEvidence]) => {
        setModels(nextModels);
        setCorr(nextCorr);
        setAmbient(nextAmbient);
        setEvidence(nextEvidence);
      })
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, []);

  const best = models?.comparison[0];
  const gauges = METRICS.map((metric) => {
    const value = Number(best?.[metric] ?? 0);
    return { label: metric, value };
  });

  const radar = METRICS.map((metric) => {
    const row: Record<string, string | number> = { metric };
    for (const model of models?.comparison ?? []) {
      row[String(model.Model)] = Number(model[metric] ?? 0);
    }
    return row;
  });

  const modelNames = (models?.comparison ?? []).map((row) => String(row.Model));

  return (
    <div className="space-y-4">
      {error ? <GlassCard className="p-4 text-sm text-amber-200">{error}</GlassCard> : null}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {gauges.map((gauge) => (
          <GlassCard key={gauge.label} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-white/45">{gauge.label}</div>
            <div className="text-3xl font-semibold mt-2">{(gauge.value * 100).toFixed(1)}%</div>
            <ProtocolBadge protocol={evidence?.headline_protocol} className="mt-2" />
            <div className="mt-3 h-1.5 rounded-full bg-white/8 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-emerald-300"
                style={{ width: `${gauge.value * 100}%` }}
              />
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <GlassCard className="p-6 overflow-x-auto">
          <h2 className="text-lg font-semibold mb-4">Model comparison</h2>
          <table className="w-full text-sm">
            <thead className="text-white/40 text-xs">
              <tr>
                {["Model", ...METRICS].map((col) => (
                  <th key={col} className="text-left font-medium pb-2 pr-3">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(models?.comparison ?? []).map((row) => (
                <tr key={String(row.Model)} className="border-t border-white/8">
                  <td className="py-2 pr-3 font-medium">{String(row.Model)}</td>
                  {METRICS.map((metric) => (
                    <td key={metric} className="py-2 pr-3 tabular-nums">
                      {(Number(row[metric]) * 100).toFixed(2)}%
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>

        <GlassCard className="p-6">
          <h2 className="text-lg font-semibold mb-4">Radar</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radar}>
                <PolarGrid stroke="rgba(255,255,255,0.12)" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 11 }} />
                <PolarRadiusAxis domain={[0.9, 1]} tick={false} axisLine={false} />
                {modelNames.map((name, index) => (
                  <Radar
                    key={name}
                    name={name}
                    dataKey={name}
                    stroke={index === 0 ? "#8B5CF6" : "#2DD4BF"}
                    fill={index === 0 ? "#8B5CF6" : "#2DD4BF"}
                    fillOpacity={0.25}
                  />
                ))}
                <Legend />
                <Tooltip contentStyle={tooltipStyle} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
      </div>

      <GlassCard className="p-6">
        <div className="flex items-start justify-between gap-3 mb-1">
          <h2 className="text-lg font-semibold">Confusion matrix</h2>
          <ProtocolBadge protocol={evidence?.headline_protocol} />
        </div>
        <p className="text-xs text-white/45 mb-4">Hold-out Random Forest · synthetic cycles</p>
        {models ? <HeatMap labels={models.confusion.labels} matrix={models.confusion.matrix} /> : null}
      </GlassCard>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <GlassCard className="p-6">
          <h2 className="text-lg font-semibold mb-4">Feature importance</h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={models?.importance ?? []}
                layout="vertical"
                margin={{ left: 24, right: 12 }}
              >
                <XAxis type="number" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="feature"
                  width={110}
                  tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 11 }}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="importance" fill="#8B5CF6" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>
        <GlassCard className="p-6">
          <h2 className="text-lg font-semibold mb-1">Per-class F1</h2>
          <p className="text-xs text-white/45 mb-4">Random Forest · per-class F1 on the hold-out test set</p>
          <ul className="space-y-2">
            {(models?.f1_per_class ?? []).map((row) => (
              <li key={row.name} className="flex items-center justify-between text-sm">
                <span className="text-white/70">{pretty(row.name)}</span>
                <span className="tabular-nums">{row.f1.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </GlassCard>
      </div>

      <GlassCard className="p-6">
        <h2 className="text-lg font-semibold mb-1">Feature correlation</h2>
        <p className="text-xs text-white/45 mb-4">Advanced · residuals and cycle metrics</p>
        {corr ? <HeatMap labels={corr.labels} matrix={corr.matrix} percent={false} /> : null}
      </GlassCard>

      <GlassCard className="p-6">
        <h2 className="text-lg font-semibold mb-1">Faults by ambient temperature</h2>
        <p className="text-xs text-white/45 mb-4">Counts on the 5000-cycle synthetic set</p>
        {ambient ? (
          <HeatMap
            labels={ambient.x_labels}
            rowLabels={ambient.y_labels}
            matrix={ambient.matrix}
            percent={false}
            integers
          />
        ) : null}
      </GlassCard>
    </div>
  );
}
