import { useEffect, useState } from "react";
import { fetchEvidenceConfusion, isAbortError, type EvidenceConfusion } from "../../api";
import { HeatMap } from "../HeatMap";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";
import { SelectField } from "../Fields";

const OPTIONS = [
  { value: "holdout-test", label: "hold-out · simulated" },
  { value: "sim2real", label: "sim2real · measured" },
];

export function ConfusionPanel() {
  const [protocol, setProtocol] = useState("holdout-test");
  const [payload, setPayload] = useState<EvidenceConfusion>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    fetchEvidenceConfusion(protocol, controller.signal)
      .then(setPayload)
      .catch((err: Error) => {
        if (isAbortError(err)) return;
        setPayload(undefined);
        setError(err.message);
      });
    return () => controller.abort();
  }, [protocol]);

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="confusion-heatmap"
      role="img"
      aria-label="Confusion matrix for the selected protocol. Cell values are written in the grid."
    >
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Confusion matrix</h2>
          <p className="text-xs text-white/60 mt-1">Same model family, two worlds. Values are written in each cell.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-52">
            <SelectField label="Protocol" value={protocol} options={OPTIONS} onChange={setProtocol} />
          </div>
          {payload ? (
            <ProtocolBadge
              protocol={{
                experiment: payload.protocol === "sim2real" ? "X5" : "X0",
                protocol: payload.protocol,
                reference: payload.protocol === "sim2real" ? "measured-knn5" : "simulated",
                features: "",
                model: "random-forest",
              }}
            />
          ) : null}
        </div>
      </div>
      {error ? (
        <p className="text-sm text-white/50">No matrix artefact for this protocol ({error}).</p>
      ) : payload ? (
        <HeatMap labels={payload.labels} matrix={payload.matrix} gap={2} />
      ) : (
        <p className="text-sm text-white/40">Loading matrix…</p>
      )}
    </GlassCard>
  );
}
