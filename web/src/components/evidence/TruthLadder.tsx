import { useState } from "react";
import type { EvidenceLadder, LadderRung } from "../../api";
import { ChartTip } from "../ChartTip";
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
  const top = rungs[0];
  const bottom = rungs[rungs.length - 1];
  const aria = `Truth ladder: from ${top ? top.percent.toFixed(1) : "—"} percent with label leak down to ${bottom ? bottom.percent.toFixed(1) : "—"} percent for the majority class, in ${rungs.length} rungs.`;

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="truth-ladder"
      role="img"
      aria-label={aria}
    >
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Truth ladder</h2>
        <p className="text-xs text-white/60 mt-1">Each rung is one logged accuracy. The label is what was removed.</p>
      </div>
      <RungList rows={simulator} max={max} />
      <div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-wide text-white/60">
        <span>simulator</span>
        <div className="flex-1 border-t border-white/25" />
        <span>NIST</span>
      </div>
      <RungList rows={nist} max={max} majority={majority} />
      {majority != null ? (
        <p className="text-[11px] text-white/60 mt-3">Dotted line: majority class at {majority.toFixed(1)}%.</p>
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
  const [hover, setHover] = useState<string | null>(null);
  return (
    <ul className="space-y-2">
      {rows.map((rung) => {
        const key = `${rung.protocol.experiment}-${rung.protocol.protocol}-${rung.cause}`;
        const active = hover === key;
        const dim = hover != null && !active;
        return (
          <li
            key={key}
            className={`relative grid grid-cols-[4rem_1fr] md:grid-cols-[4.5rem_1fr_minmax(12rem,2fr)] gap-3 items-center min-h-8 transition-opacity duration-150 ${dim ? "opacity-60" : ""}`}
            onMouseEnter={() => setHover(key)}
            onMouseLeave={() => setHover(null)}
          >
            <div className="text-sm tabular-nums font-medium">{rung.percent.toFixed(1)}%</div>
            <div className={`relative h-7 rounded-full bg-white/8 overflow-hidden ${active ? "ring-1 ring-white/25" : ""}`}>
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
            <div className="min-w-0 col-span-2 md:col-span-1">
              <div className="text-sm text-white/80 leading-tight">{rung.cause}</div>
              <ProtocolBadge protocol={rung.protocol} className="mt-1" />
            </div>
            {active ? (
              <ChartTip>
                {rung.percent.toFixed(1)}% · {rung.cause}
                <br />
                {rung.protocol.experiment} · {rung.protocol.protocol}
              </ChartTip>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
