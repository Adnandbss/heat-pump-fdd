import { useState } from "react";
import type { EvidenceDomain } from "../../api";
import { ChartTip } from "../ChartTip";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

type Props = { data?: EvidenceDomain };

export function DomainSeverity({ data }: Props) {
  const domain = data?.domain ?? [];
  const severity = data?.severity ?? [];
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(1, ...domain.map((row) => row.accuracy), ...severity.flatMap((row) => [row.binary, row.multiclass].filter((v): v is number => v != null)));
  const worst = severity
    .map((row) => row.multiclass)
    .filter((value): value is number => value != null)
    .sort((a, b) => a - b)[0];
  const aria = `Domain hold-out stays near the random control; 4-class severity transfer falls to ${worst != null ? (worst * 100).toFixed(1) : "—"} percent.`;

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="domain-severity"
      role="img"
      aria-label={aria}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Domain holds; severity does not</h2>
          <p className="text-xs text-white/60 mt-1">X4 · same simulator, a split the model has not seen.</p>
        </div>
        <ProtocolBadge protocol={data?.badge} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          <h3 className="text-sm text-white/75 mb-3">The domain holds</h3>
          <ul className="space-y-2">
            {domain.map((row) => {
              const active = hover === row.key;
              const dim = hover != null && !active;
              const lo = row.wilson ? (row.wilson.low / max) * 100 : null;
              const hi = row.wilson ? (row.wilson.high / max) * 100 : null;
              return (
                <li
                  key={row.key}
                  className={`relative grid grid-cols-[7.5rem_1fr_3rem] gap-2 items-center min-h-8 transition-opacity duration-150 ${dim ? "opacity-60" : ""}`}
                  onMouseEnter={() => setHover(row.key)}
                  onMouseLeave={() => setHover(null)}
                >
                  <div className="text-xs text-white/75 leading-tight">{row.label}</div>
                  <div className={`relative h-6 rounded-full bg-white/8 overflow-visible ${active ? "ring-1 ring-white/25" : ""}`}>
                    <div
                      className="h-full rounded-full bg-[#A78BFA]"
                      style={{ width: `${(row.accuracy / max) * 100}%` }}
                    />
                    {lo != null && hi != null ? (
                      <div
                        className="pointer-events-none absolute top-1/2 h-3 -translate-y-1/2 border-x border-white/70"
                        style={{ left: `${lo}%`, width: `${Math.max(hi - lo, 0.4)}%` }}
                      />
                    ) : null}
                  </div>
                  <div className="text-[11px] tabular-nums text-white/70">{row.accuracy.toFixed(3)}</div>
                  {active ? (
                    <ChartTip>
                      {row.label}: {row.accuracy.toFixed(3)}
                      {row.n != null ? ` · n=${row.n}` : ""}
                      {row.wilson ? ` · Wilson ${row.wilson.low.toFixed(3)}–${row.wilson.high.toFixed(3)}` : ""}
                      <br />
                      {row.protocol.protocol}
                    </ChartTip>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
        <div>
          <h3 className="text-sm text-white/75 mb-3">Severity breaks it</h3>
          <ul className="space-y-4">
            {severity.map((row) => (
              <li key={row.key} className="space-y-1.5">
                <div className="text-xs text-white/70">{row.label}</div>
                {[
                  { key: `${row.key}-bin`, label: "binary", value: row.binary, n: row.n_binary, color: "#7DD3FC", protocol: row.binary_protocol },
                  { key: `${row.key}-4`, label: "4-class", value: row.multiclass, n: row.n_multiclass, color: "#F5C542", protocol: row.multiclass_protocol },
                ].map((bar) => {
                  const active = hover === bar.key;
                  const dim = hover != null && !active;
                  return (
                    <div
                      key={bar.key}
                      className={`relative grid grid-cols-[4.5rem_1fr_3rem] gap-2 items-center min-h-7 transition-opacity duration-150 ${dim ? "opacity-60" : ""}`}
                      onMouseEnter={() => setHover(bar.key)}
                      onMouseLeave={() => setHover(null)}
                    >
                      <div className="text-[11px] text-white/60">{bar.label}</div>
                      <div className={`h-5 rounded-full bg-white/8 overflow-hidden ${active ? "ring-1 ring-white/25" : ""}`}>
                        {bar.value != null ? (
                          <div className="h-full rounded-full" style={{ width: `${(bar.value / max) * 100}%`, background: bar.color }} />
                        ) : null}
                      </div>
                      <div className="text-[11px] tabular-nums text-white/70">
                        {bar.value == null ? "—" : bar.value.toFixed(3)}
                      </div>
                      {active && bar.value != null ? (
                        <ChartTip>
                          {row.label} · {bar.label}: {bar.value.toFixed(3)}
                          {bar.n != null ? ` · n=${bar.n}` : ""}
                          {bar.protocol ? ` · ${bar.protocol.protocol}` : ""}
                        </ChartTip>
                      ) : null}
                    </div>
                  );
                })}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {data?.caption ? <p className="text-sm text-white/70 mt-5">{data.caption}</p> : null}
    </GlassCard>
  );
}
