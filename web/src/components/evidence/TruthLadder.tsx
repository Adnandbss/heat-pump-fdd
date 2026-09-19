import type { EvidenceLadder, LadderRung } from "../../api";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

type Props = { data?: EvidenceLadder };

function shade(t: number) {
  const light = 78 - t * 42;
  return `hsl(258 75% ${light}%)`;
}

export function TruthLadder({ data }: Props) {
  const rungs = data?.rungs ?? [];
  const max = Math.max(...rungs.map((rung) => rung.percent), 1);
  const simulator = rungs.filter((rung) => rung.band === "simulator");
  const nist = rungs.filter((rung) => rung.band === "nist");
  const majority = data?.majority != null ? data.majority * 100 : undefined;

  return (
    <GlassCard className="p-6" data-testid="truth-ladder">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Truth ladder</h2>
        <p className="text-xs text-white/45 mt-1">Each rung is one logged accuracy. The label is what was removed.</p>
      </div>
      <RungList rows={simulator} max={max} />
      <div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-wide text-white/40">
        <span>simulator</span>
        <div className="flex-1 border-t border-white/25" />
        <span>NIST</span>
      </div>
      <RungList rows={nist} max={max} majority={majority} />
      {majority != null ? (
        <p className="text-[11px] text-white/40 mt-3">Dotted line: majority class at {majority.toFixed(1)}%.</p>
      ) : null}
    </GlassCard>
  );
}

function RungList({
  rows,
  max,
  majority,
}: {
  rows: LadderRung[];
  max: number;
  majority?: number;
}) {
  return (
    <ul className="space-y-2">
      {rows.map((rung) => (
        <li key={`${rung.protocol.experiment}-${rung.protocol.protocol}-${rung.cause}`} className="grid grid-cols-[4.5rem_1fr_minmax(12rem,2fr)] gap-3 items-center">
          <div className="text-sm tabular-nums font-medium">{rung.percent.toFixed(1)}%</div>
          <div className="relative h-7 rounded-full bg-white/8 overflow-hidden">
            {majority != null ? (
              <div
                className="pointer-events-none absolute top-0 bottom-0 border-l border-dashed border-white/50"
                style={{ left: `${(majority / max) * 100}%` }}
              />
            ) : null}
            <div
              className="h-full rounded-full"
              style={{
                width: `${(rung.percent / max) * 100}%`,
                background: rung.majority
                  ? "repeating-linear-gradient(-45deg, rgba(255,255,255,0.4) 0 6px, transparent 6px 11px)"
                  : shade(rung.percent / max),
              }}
            />
          </div>
          <div className="min-w-0">
            <div className="text-sm text-white/80 leading-tight">{rung.cause}</div>
            <ProtocolBadge protocol={rung.protocol} className="mt-1" />
          </div>
        </li>
      ))}
    </ul>
  );
}
