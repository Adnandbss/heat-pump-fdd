import { useState } from "react";
import type { EvidenceFeatures } from "../../api";
import { ChartTip } from "../ChartTip";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

const COLORS: Record<string, string> = {
  "23-col": "#A78BFA",
  "23-col-minus-dead": "#7DD3FC",
  residuals: "#F5C542",
  "residuals+conditions": "#C4B5FD",
};

type Props = { data?: EvidenceFeatures };

export function FeatureContract({ data }: Props) {
  const series = (data?.series ?? []).filter((row) => row.holdout != null && row.domain != null);
  const values = series.flatMap((row) => [row.holdout as number, row.domain as number]);
  const yMin = values.length ? Math.min(...values) - 0.04 : 0;
  const yMax = values.length ? Math.max(...values) + 0.04 : 1;
  const width = 640;
  const height = 240;
  const left = 90;
  const right = 250;
  const top = 18;
  const bottom = height - 28;
  const [hover, setHover] = useState<string | null>(null);

  function y(value: number) {
    return top + ((yMax - value) / (yMax - yMin)) * (bottom - top);
  }

  const residuals = series.find((row) => row.features === "residuals");
  const full = series.find((row) => row.features === "23-col");
  const drop =
    residuals?.holdout != null && full?.holdout != null ? (full.holdout - residuals.holdout) * 100 : null;
  const aria = `Feature-contract slopegraph: residuals-only loses ${drop == null ? "several" : drop.toFixed(0)} points versus the full 23-column set and was rejected.`;

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="feature-contract"
      role="img"
      aria-label={aria}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h2 className="text-lg font-semibold">A prescription, measured then rejected</h2>
          <p className="text-xs text-white/60 mt-1">{data?.note}</p>
        </div>
        <ProtocolBadge protocol={data?.badge} label="P5 · simulated" />
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[480px] h-60">
          <text x={left} y={14} textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="11">
            Hold-out
          </text>
          <text x={right} y={14} textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="11">
            T_set &gt; 48 °C
          </text>
          {series.map((row) => {
            const color = COLORS[row.features] ?? "#A78BFA";
            const y0 = y(row.holdout as number);
            const y1 = y(row.domain as number);
            const dim = hover != null && hover !== row.features;
            return (
              <g
                key={row.features}
                className="cursor-pointer"
                opacity={dim ? 0.4 : 1}
                onMouseEnter={() => setHover(row.features)}
                onMouseLeave={() => setHover(null)}
              >
                <line x1={left} y1={y0} x2={right} y2={y1} stroke={color} strokeWidth="10" strokeOpacity="0" />
                <line x1={left} y1={y0} x2={right} y2={y1} stroke={color} strokeWidth="2" />
                <circle cx={left} cy={y0} r="4.5" fill={color} />
                <circle cx={right} cy={y1} r="4.5" fill={color} />
                <text x={left - 10} y={y0 + 4} textAnchor="end" fill="rgba(255,255,255,0.8)" fontSize="11">
                  {(row.holdout as number).toFixed(3)}
                </text>
                <text x={right + 10} y={y1 + 4} fill="rgba(255,255,255,0.85)" fontSize="11">
                  {(row.domain as number).toFixed(3)} {row.features}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {hover ? (
        <div className="relative h-0">
          <div className="-mt-2">
            <ChartTip>
              {hover}: hold-out {series.find((row) => row.features === hover)?.holdout?.toFixed(3)} → domain{" "}
              {series.find((row) => row.features === hover)?.domain?.toFixed(3)}
            </ChartTip>
          </div>
        </div>
      ) : null}
    </GlassCard>
  );
}
