import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchActivity,
  fetchChallenges,
  fetchDataset,
  fetchDistribution,
  fetchEvidenceSummary,
  fetchOverview,
  fetchScatter,
  fetchStats,
  isAbortError,
  type Activity,
  type Challenge,
  type DatasetPayload,
  type EvidenceSummary,
  type Overview,
  type Stats,
} from "../api";
import { colorFor, tooltipStyle } from "../lib";
import { ActivityChart } from "../components/ActivityChart";
import { BoxPlot } from "../components/BoxPlot";
import { CalendarWidget } from "../components/CalendarWidget";
import { Challenges } from "../components/Challenges";
import { GlassCard } from "../components/GlassCard";
import { MiniStats } from "../components/MiniStats";
import { OutputWidget } from "../components/OutputWidget";
import { OverviewDonut } from "../components/OverviewDonut";
import { ProtocolBadge } from "../components/ProtocolBadge";
import { SelectField } from "../components/Fields";
import { Skeleton } from "../components/Skeleton";

export function InsightsPage() {
  const [stats, setStats] = useState<Stats>();
  const [overview, setOverview] = useState<Overview>();
  const [activity, setActivity] = useState<Activity>();
  const [challenges, setChallenges] = useState<Challenge[]>();
  const [dataset, setDataset] = useState<DatasetPayload>();
  const [evidence, setEvidence] = useState<EvidenceSummary>();
  const [feature, setFeature] = useState("superheat");
  const [xCol, setXCol] = useState("delta_T_evap");
  const [yCol, setYCol] = useState("delta_T_cond");
  const [boxes, setBoxes] = useState<Awaited<ReturnType<typeof fetchDistribution>>>();
  const [scatter, setScatter] = useState<Awaited<ReturnType<typeof fetchScatter>>>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchStats("Condenser_Fouling", controller.signal),
      fetchOverview(controller.signal),
      fetchActivity(controller.signal),
      fetchChallenges(controller.signal),
      fetchDataset(controller.signal),
      fetchEvidenceSummary(controller.signal).catch((err: Error) => {
        if (isAbortError(err)) throw err;
        return undefined;
      }),
    ])
      .then(([nextStats, nextOverview, nextActivity, nextChallenges, nextDataset, nextEvidence]) => {
        setStats(nextStats);
        setOverview(nextOverview);
        setActivity(nextActivity);
        setChallenges(nextChallenges.challenges);
        setDataset(nextDataset);
        setEvidence(nextEvidence);
        if (nextDataset.columns.includes("superheat")) setFeature("superheat");
      })
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchDistribution(feature, controller.signal)
      .then(setBoxes)
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, [feature]);

  useEffect(() => {
    const controller = new AbortController();
    fetchScatter(xCol, yCol, controller.signal)
      .then(setScatter)
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, [xCol, yCol]);

  const kpis = useMemo(() => {
    return [
      { label: "Samples", value: dataset ? dataset.n_samples.toLocaleString() : "—" },
      { label: "Fault classes", value: dataset ? String(dataset.n_classes) : "—" },
      {
        label: "% Normal",
        value: dataset ? `${(dataset.normal_share * 100).toFixed(0)}%` : "—",
      },
      {
        label: "Hold-out accuracy",
        value: overview?.accuracy != null ? `${(overview.accuracy * 100).toFixed(1)}%` : "—",
      },
    ];
  }, [dataset, overview]);

  const columns = (dataset?.columns ?? []).map((col) => ({ value: col, label: col }));

  const loading = !dataset && !overview && !error;

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          <Skeleton className="h-[104px]" />
          <Skeleton className="h-[104px]" />
          <Skeleton className="h-[104px]" />
          <Skeleton className="h-[104px]" />
        </div>
        <Skeleton className="h-[22rem]" />
        <Skeleton className="h-[20rem]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <GlassCard className="p-4 text-sm text-amber-200">Could not load overview ({error}).</GlassCard>
      ) : null}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {kpis.map((kpi) => (
          <GlassCard key={kpi.label} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-white/60">{kpi.label}</div>
            <div className="text-2xl font-semibold mt-2">{kpi.value}</div>
            {kpi.label === "Hold-out accuracy" ? (
              <ProtocolBadge protocol={evidence?.headline_protocol} className="mt-2" />
            ) : null}
          </GlassCard>
        ))}
      </div>
      {normalShareHint(dataset)}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <section className="xl:col-span-5">
          <ActivityChart data={activity} />
        </section>
        <section className="xl:col-span-3">
          <MiniStats stats={stats} />
        </section>
        <section className="xl:col-span-4">
          <OverviewDonut overview={overview} stats={stats} />
        </section>
        <section className="xl:col-span-5">
          <Challenges challenges={challenges} />
        </section>
        <section className="xl:col-span-4">
          <CalendarWidget activity={activity} />
        </section>
        <section className="xl:col-span-3">
          <OutputWidget stats={stats} />
        </section>
      </div>

      <GlassCard className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">Data explorer</h2>
            <p className="text-xs text-white/45 mt-1">
              Feature distributions and residual scatter from the 5000-cycle set
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <SelectField
            label="Feature"
            value={feature}
            options={columns}
            onChange={setFeature}
          />
          <SelectField label="Scatter X" value={xCol} options={columns} onChange={setXCol} />
          <SelectField label="Scatter Y" value={yCol} options={columns} onChange={setYCol} />
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm mb-3 text-white/70">Box plot · {feature}</h3>
            <BoxPlot boxes={boxes?.boxes ?? []} />
          </div>
          <div>
            <h3 className="text-sm mb-3 text-white/70">
              {xCol} vs {yCol}
            </h3>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis type="number" dataKey="x" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <YAxis type="number" dataKey="y" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value) => Number(value).toFixed(2)}
                  />
                  <Scatter data={scatter?.points ?? []} fill="#8B5CF6">
                    {(scatter?.points ?? []).map((point, index) => (
                      <Cell key={index} fill={colorFor(point.fault_type)} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </GlassCard>
    </div>
  );
}

function normalShareHint(dataset?: DatasetPayload) {
  if (!dataset) return null;
  return (
    <p className="text-xs text-white/35">
      Synthetic CoolProp cycles · {(dataset.normal_share * 100).toFixed(0)}% healthy operating
      points in the labelled set.
    </p>
  );
}
