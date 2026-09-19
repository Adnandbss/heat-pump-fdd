import type { EvidenceProtocols } from "../../api";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

const COLORS: Record<string, string> = {
  raw: "#94A3B8",
  residuals: "#A78BFA",
  "raw+residuals": "#7DD3FC",
  "residuals+conditions": "#C4B5FD",
};

type Props = { data?: EvidenceProtocols };

export function ProtocolSlope({ data }: Props) {
  const series = (data?.series ?? []).filter(
    (row) => row.random_cv != null && row.lomo != null,
  );
  const values = series.flatMap((row) => [row.random_cv as number, row.lomo as number]);
  const yMin = values.length ? Math.min(...values) - 0.04 : 0;
  const yMax = 1;
  const width = 640;
  const height = 280;
  const left = 90;
  const right = 250;
  const top = 18;
  const bottom = height - 28;

  function y(value: number) {
    return top + ((yMax - value) / (yMax - yMin)) * (bottom - top);
  }

  const warn = series.find((row) => row.protocol_cv)?.protocol_cv;
  const honest = series.find((row) => row.protocol_lomo)?.protocol_lomo;

  return (
    <GlassCard className="p-6" data-testid="protocol-slope">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h2 className="text-lg font-semibold">Protocol outweighs features</h2>
          <p className="text-xs text-white/45 mt-1">Slope is the gap between random CV and leave-one-machine-out.</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <ProtocolBadge protocol={warn} />
          <ProtocolBadge protocol={honest} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[520px] h-72">
          <text x={left} y={14} textAnchor="middle" fill="rgba(255,255,255,0.45)" fontSize="11">
            Random CV
          </text>
          <text x={right} y={14} textAnchor="middle" fill="rgba(255,255,255,0.45)" fontSize="11">
            LOMO
          </text>
          {series.map((row) => {
            const color = COLORS[row.features] ?? "#A78BFA";
            const y0 = y(row.random_cv as number);
            const y1 = y(row.lomo as number);
            return (
              <g key={row.features}>
                <line x1={left} y1={y0} x2={right} y2={y1} stroke={color} strokeWidth="2" />
                <circle cx={left} cy={y0} r="4.5" fill={color} />
                <circle cx={right} cy={y1} r="4.5" fill={color} />
                <text x={left - 10} y={y0 + 4} textAnchor="end" fill="rgba(255,255,255,0.8)" fontSize="11">
                  {(row.random_cv as number).toFixed(3)}
                </text>
                <text x={right + 10} y={y1 + 4} fill="rgba(255,255,255,0.85)" fontSize="11">
                  {(row.lomo as number).toFixed(3)} {row.features}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </GlassCard>
  );
}
