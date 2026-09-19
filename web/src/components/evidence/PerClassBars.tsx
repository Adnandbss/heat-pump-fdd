import type { EvidencePerClass } from "../../api";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

const SERIES = [
  { key: "simulated" as const, label: "simulator", color: "#A78BFA" },
  { key: "target" as const, label: "NIST target", color: "#7DD3FC" },
  { key: "transferred" as const, label: "transferred", color: "#F5C542" },
];

type Props = { data?: EvidencePerClass };

export function PerClassBars({ data }: Props) {
  const rows = data?.rows ?? [];
  const numeric = rows.flatMap((row) => [row.simulated, row.target, row.transferred]).filter(
    (value): value is number => value != null,
  );
  const max = Math.max(...numeric, 0.01);

  return (
    <GlassCard className="p-6" data-testid="per-class-bars">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Per-class F1</h2>
          <p className="text-xs text-white/45 mt-1">Sorted on the NIST target-machine ceiling. Missing bars are unmeasurable, not zero.</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <ProtocolBadge protocol={data?.protocols.simulated} />
          <ProtocolBadge protocol={data?.protocols.target} />
          <ProtocolBadge protocol={data?.protocols.transferred} />
        </div>
      </div>
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.display} className="grid grid-cols-[7.5rem_1fr] gap-3 items-center">
            <div className="text-sm text-white/75 truncate">{row.display.replace(/_/g, " ")}</div>
            <div className="space-y-1">
              {SERIES.map((series) => {
                const value = row[series.key];
                return (
                  <div key={series.key} className="flex items-center gap-2">
                    <div className="h-2.5 flex-1 rounded-full bg-white/8 overflow-hidden">
                      {value != null ? (
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${(value / max) * 100}%`, background: series.color }}
                        />
                      ) : (
                        <div className="h-full w-full bg-transparent" />
                      )}
                    </div>
                    <div className="w-28 text-[11px] tabular-nums text-white/55">
                      {series.label} {value == null ? "—" : value.toFixed(3)}
                    </div>
                  </div>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      <ul className="mt-4 space-y-1 text-xs text-white/50">
        {(data?.notes ?? []).map((note) => (
          <li key={note}>→ {note}</li>
        ))}
      </ul>
    </GlassCard>
  );
}
