import { useState } from "react";
import type { EvidenceCalibration } from "../../api";
import { ChartTip } from "../ChartTip";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

type Props = { data?: EvidenceCalibration };

export function CalibrationBudget({ data }: Props) {
  const points = (data?.points ?? []).filter((point) => point.accuracy != null);
  const values = points.map((point) => point.accuracy as number);
  const yMin = values.length ? Math.min(...values) - 0.04 : 0;
  const yMax = values.length ? Math.max(...values) + 0.04 : 1;
  const width = 640;
  const height = 240;
  const left = 56;
  const right = width - 24;
  const top = 16;
  const bottom = height - 36;
  const [hover, setHover] = useState<string | null>(null);
  const n50 = points.find((point) => point.n_label === "50")?.accuracy;
  const n0 = points.find((point) => point.n_label === "0")?.accuracy;
  const nAll = points.find((point) => point.n_label === "all")?.accuracy;
  const recovered =
    n50 != null && n0 != null && nAll != null && nAll > n0
      ? ((n50 - n0) / (nAll - n0)) * 100
      : null;
  const aria = `Calibration budget: ${points.length} points from a transferred reference to a fully calibrated one.${recovered == null ? "" : ` Fifty healthy tests recover about ${recovered.toFixed(0)} percent of the gain.`}`;

  function x(index: number) {
    if (points.length <= 1) return (left + right) / 2;
    return left + (index / (points.length - 1)) * (right - left);
  }

  function y(value: number) {
    return top + ((yMax - value) / (yMax - yMin)) * (bottom - top);
  }

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point.accuracy as number)}`)
    .join(" ");

  return (
    <GlassCard
      className="relative p-6 transition-opacity duration-200"
      data-testid="calibration-budget"
      role="img"
      aria-label={aria}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h2 className="text-lg font-semibold">What calibration costs</h2>
          <p className="text-xs text-white/60 mt-1">
            Healthy tests from the target machine, held out of the test set. Leave-one-machine-out.
          </p>
        </div>
        <ProtocolBadge protocol={data?.badge} />
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[480px] h-60">
          {path ? (
            <path d={path} fill="none" stroke="#A78BFA" strokeWidth="2.2" />
          ) : null}
          {points.map((point, index) => {
            const active = hover === point.n_label;
            const dim = hover != null && !active;
            return (
              <g
                key={point.n_label}
                className="cursor-pointer"
                opacity={dim ? 0.4 : 1}
                onMouseEnter={() => setHover(point.n_label)}
                onMouseLeave={() => setHover(null)}
              >
                <circle cx={x(index)} cy={y(point.accuracy as number)} r={active ? 6 : 4.5} fill="#A78BFA" />
                <text x={x(index)} y={bottom + 18} textAnchor="middle" fill="rgba(255,255,255,0.55)" fontSize="11">
                  n = {point.n_label}
                </text>
                {active ? (
                  <ChartTip>
                    n = {point.n_label}: {(point.accuracy as number).toFixed(3)}
                    {point.f1 != null ? ` · F1 ${point.f1.toFixed(3)}` : ""}
                    {point.protocol ? ` · ${point.protocol.protocol}` : ""}
                  </ChartTip>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
      {data?.caption ? <p className="text-[11px] text-white/60 mt-1">{data.caption}</p> : null}
    </GlassCard>
  );
}
