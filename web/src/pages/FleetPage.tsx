import { useEffect, useState } from "react";
import { fetchFleet, isAbortError, type FleetResponse, type FleetUnit } from "../api";
import { pretty } from "../lib";
import { GlassCard } from "../components/GlassCard";
import { Skeleton } from "../components/Skeleton";

const ACTION_LABEL: Record<FleetUnit["action"], string> = {
  dispatch: "Dispatch",
  engineering_review: "Engineering review",
  monitor: "Monitor",
  no_action: "No action",
};

const ACTION_STYLE: Record<FleetUnit["action"], string> = {
  dispatch: "bg-violet-400/20 text-violet-100 border-violet-300/30",
  engineering_review: "bg-amber-400/15 text-amber-100 border-amber-300/30",
  monitor: "bg-sky-400/15 text-sky-100 border-sky-300/30",
  no_action: "bg-white/5 text-white/55 border-white/10",
};

const EVIDENCE_LABEL: Record<FleetUnit["evidence"]["status"], string> = {
  transfers: "Validated",
  does_not_transfer: "Does not transfer",
  untested: "Untested",
};

const EVIDENCE_STYLE: Record<FleetUnit["evidence"]["status"], string> = {
  transfers: "text-emerald-200 border-emerald-300/30",
  does_not_transfer: "text-amber-200 border-amber-300/30",
  untested: "text-white/55 border-white/15",
};

export function FleetPage() {
  const [data, setData] = useState<FleetResponse>();
  const [error, setError] = useState<string>();
  const [showTruth, setShowTruth] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchFleet({}, controller.signal)
      .then(setData)
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, []);

  if (error) return <GlassCard className="p-4 text-sm text-amber-200">{error}</GlassCard>;
  if (!data) return <Skeleton className="h-96" />;

  const { summary, policy } = data;
  const cards = [
    { key: "units", label: "Units", value: summary.units },
    { key: "dispatch", label: "Dispatch", value: summary.dispatch },
    { key: "engineering_review", label: "Engineering review", value: summary.engineering_review },
    { key: "monitor", label: "Monitor", value: summary.monitor },
    { key: "no_action", label: "No action", value: summary.no_action },
    { key: "held_back", label: "Held back by the evidence gate", value: summary.held_back },
  ];

  return (
    <div className="space-y-4">
      <GlassCard className="p-4 text-xs text-white/60" data-testid="fleet-notice">
        {data.notice}
      </GlassCard>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3" data-testid="fleet-summary">
        {cards.map((card) => (
          <GlassCard key={card.key} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-white/45">{card.label}</div>
            <div className="text-2xl font-semibold mt-2 tabular-nums">{card.value}</div>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="p-6" data-testid="fleet-table">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold">Service queue</h2>
            <p className="text-xs text-white/45 mt-1">
              Dispatch requires {policy.evidence_experiment} / {policy.evidence_protocol} F1 of at least{" "}
              {policy.evidence_f1_min.toFixed(2)} and a confidence of at least {policy.confidence_min.toFixed(2)}
              {policy.validated_only ? "" : " · evidence gate off"}
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-white/70">
            <input
              type="checkbox"
              checked={showTruth}
              onChange={(event) => setShowTruth(event.target.checked)}
            />
            Show simulated ground truth
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <caption className="sr-only">Units sorted by what the service team should do next</caption>
            <thead className="text-white/60">
              <tr>
                <th scope="col" className="text-left font-medium pb-2 pr-3">Unit</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3 hidden md:table-cell">Conditions</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3">Diagnosis</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3">Confidence</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3">Evidence on measured units</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3">Action</th>
                <th scope="col" className="text-left font-medium pb-2 pr-3 hidden lg:table-cell">Instruction</th>
                {showTruth ? <th scope="col" className="text-left font-medium pb-2 pr-3">Injected</th> : null}
              </tr>
            </thead>
            <tbody>
              {data.units.map((unit) => (
                <tr
                  key={unit.unit_id}
                  data-testid="fleet-row"
                  className="border-t border-white/8 transition-colors duration-150 hover:bg-white/5"
                >
                  <td className="py-2 pr-3 font-medium whitespace-nowrap">{unit.unit_id}</td>
                  <td className="py-2 pr-3 hidden md:table-cell text-white/55 tabular-nums whitespace-nowrap">
                    {unit.T_source.toFixed(1)} → {unit.T_sink.toFixed(1)} °C · {(unit.speed_ratio * 100).toFixed(0)}%
                  </td>
                  <td className="py-2 pr-3">{pretty(unit.diagnosis)}</td>
                  <td className="py-2 pr-3 tabular-nums">{(unit.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2 pr-3">
                    <span
                      data-testid="evidence-badge"
                      data-status={unit.evidence.status}
                      title={
                        unit.evidence.f1 != null
                          ? `${unit.evidence.experiment} / ${unit.evidence.protocol} · F1 ${unit.evidence.f1.toFixed(3)}${
                              unit.evidence.n != null ? ` · n ${unit.evidence.n}` : ""
                            }`
                          : `No ${unit.evidence.experiment} / ${unit.evidence.protocol} row for this class`
                      }
                      className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                        EVIDENCE_STYLE[unit.evidence.status]
                      }`}
                    >
                      {EVIDENCE_LABEL[unit.evidence.status]}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      data-testid="action-pill"
                      data-action={unit.action}
                      className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] ${ACTION_STYLE[unit.action]}`}
                    >
                      {ACTION_LABEL[unit.action]}
                    </span>
                  </td>
                  <td className="py-2 pr-3 hidden lg:table-cell text-white/60 max-w-[18rem]">{unit.instruction}</td>
                  {showTruth ? (
                    <td
                      className={`py-2 pr-3 ${
                        unit.ground_truth === unit.diagnosis ? "text-white/55" : "text-amber-200"
                      }`}
                    >
                      {pretty(unit.ground_truth)}
                      {unit.ground_truth === "Normal" ? "" : ` · ${unit.ground_truth_severity.toFixed(2)}`}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
