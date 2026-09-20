import { useState } from "react";
import type { EvidenceRules } from "../../api";
import { ChartTip } from "../ChartTip";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

const COLORS: Record<string, string> = {
  "rule-table": "#94A3B8",
  "decision-tree-d3": "#7DD3FC",
  "gradient-boosting": "#A78BFA",
};

type Props = { data?: EvidenceRules };

export function RulesBars({ data }: Props) {
  const bars = data?.bars ?? [];
  const majority = data?.majority;
  const values = bars.map((bar) => bar.accuracy).filter((value): value is number => value != null);
  if (majority != null) values.push(majority);
  const max = Math.max(...values, 0.01);
  const [hover, setHover] = useState<string | null>(null);
  const table = bars.find((bar) => bar.model === "rule-table")?.accuracy;
  const boost = bars.find((bar) => bar.model === "gradient-boosting")?.accuracy;
  const aria = `Sign table versus depth-3 tree versus gradient boosting on LOMO NIST. Boosting ${boost == null ? "" : (boost * 100).toFixed(1)} percent, sign table ${table == null ? "" : (table * 100).toFixed(1)} percent.`;

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="rules-bars"
      role="img"
      aria-label={aria}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Does the model beat a sign table?</h2>
          <p className="text-xs text-white/60 mt-1">Calibrated healthy reference · leave-one-machine-out.</p>
        </div>
        <ProtocolBadge protocol={data?.badge} />
      </div>
      <ul className="space-y-3">
        {bars.map((bar) => {
          const value = bar.accuracy;
          const active = hover === bar.model;
          const dim = hover != null && !active;
          return (
            <li
              key={bar.model}
              className={`relative grid grid-cols-[8rem_1fr_3.5rem] gap-3 items-center min-h-9 transition-opacity duration-150 ${dim ? "opacity-60" : ""}`}
              onMouseEnter={() => setHover(bar.model)}
              onMouseLeave={() => setHover(null)}
            >
              <div className="text-sm text-white/75">{bar.label}</div>
              <div className={`relative h-7 rounded-full bg-white/8 overflow-hidden ${active ? "ring-1 ring-white/25" : ""}`}>
                {majority != null ? (
                  <div
                    className="pointer-events-none absolute top-0 bottom-0 border-l border-dashed border-white/50"
                    style={{ left: `${(majority / max) * 100}%` }}
                  />
                ) : null}
                {value != null ? (
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(value / max) * 100}%`, background: COLORS[bar.model] ?? "#A78BFA" }}
                  />
                ) : null}
              </div>
              <div className="text-sm tabular-nums text-white/70">{value == null ? "—" : value.toFixed(3)}</div>
              {active && value != null ? (
                <ChartTip>
                  {bar.label}: {value.toFixed(3)}
                  {bar.protocol ? ` · ${bar.protocol.protocol} · ${bar.protocol.reference}` : ""}
                </ChartTip>
              ) : null}
            </li>
          );
        })}
      </ul>
      {majority != null ? (
        <p className="text-[11px] text-white/60 mt-3">
          Dotted line: majority class at {majority.toFixed(3)}.
        </p>
      ) : null}
    </GlassCard>
  );
}
