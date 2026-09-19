import { useEffect, useState } from "react";
import {
  fetchEvidenceLadder,
  fetchEvidencePerClass,
  fetchEvidenceProtocols,
  fetchEvidenceReferences,
  fetchEvidenceRuns,
  fetchEvidenceSummary,
  isAbortError,
  type EvidenceLadder,
  type EvidencePerClass,
  type EvidenceProtocols,
  type EvidenceReferences,
  type EvidenceRuns,
  type EvidenceSummary,
} from "../api";
import { CalibrationCurve } from "../components/evidence/CalibrationCurve";
import { ConfusionPanel } from "../components/evidence/ConfusionPanel";
import { PerClassBars } from "../components/evidence/PerClassBars";
import { ProtocolSlope } from "../components/evidence/ProtocolSlope";
import { RunsTable } from "../components/evidence/RunsTable";
import { TruthLadder } from "../components/evidence/TruthLadder";
import { ProtocolBadge } from "../components/ProtocolBadge";
import { GlassCard } from "../components/GlassCard";

export function EvidencePage() {
  const [summary, setSummary] = useState<EvidenceSummary>();
  const [ladder, setLadder] = useState<EvidenceLadder>();
  const [protocols, setProtocols] = useState<EvidenceProtocols>();
  const [references, setReferences] = useState<EvidenceReferences>();
  const [perClass, setPerClass] = useState<EvidencePerClass>();
  const [runs, setRuns] = useState<EvidenceRuns>();
  const [filters, setFilters] = useState({ experiment: "", protocol: "", model: "", label: "" });
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchEvidenceSummary(controller.signal),
      fetchEvidenceLadder(controller.signal),
      fetchEvidenceProtocols(controller.signal),
      fetchEvidenceReferences(controller.signal),
      fetchEvidencePerClass(controller.signal),
    ])
      .then(([nextSummary, nextLadder, nextProtocols, nextReferences, nextPerClass]) => {
        setSummary(nextSummary);
        setLadder(nextLadder);
        setProtocols(nextProtocols);
        setReferences(nextReferences);
        setPerClass(nextPerClass);
      })
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchEvidenceRuns({ ...filters, offset, limit: 50 }, controller.signal)
      .then((next) => {
        setRuns((prev) =>
          offset === 0 || !prev
            ? next
            : { ...next, rows: [...prev.rows, ...next.rows] },
        );
      })
      .catch((err: Error) => {
        if (!isAbortError(err)) setError(err.message);
      });
    return () => controller.abort();
  }, [filters, offset]);

  return (
    <div className="space-y-4" data-testid="evidence-page">
      {error ? (
        <GlassCard className="p-4 text-sm text-amber-200">Could not load evidence ({error}).</GlassCard>
      ) : null}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {(summary?.cards ?? []).map((card) => (
          <GlassCard key={card.key} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-white/45">{card.label}</div>
            <div className="text-2xl font-semibold mt-2">
              {card.key === "headline" && card.value ? `${card.value}%` : card.value || "—"}
            </div>
            {card.protocol ? <ProtocolBadge protocol={card.protocol} className="mt-2" /> : null}
          </GlassCard>
        ))}
      </div>

      <TruthLadder data={ladder} />
      <ProtocolSlope data={protocols} />
      <CalibrationCurve data={references} />
      <PerClassBars data={perClass} />
      <ConfusionPanel />
      <RunsTable
        data={runs}
        experiment={filters.experiment}
        protocol={filters.protocol}
        model={filters.model}
        label={filters.label}
        onFilter={(next) => {
          setOffset(0);
          setFilters(next);
        }}
        onMore={() => setOffset((prev) => prev + 50)}
      />
    </div>
  );
}
