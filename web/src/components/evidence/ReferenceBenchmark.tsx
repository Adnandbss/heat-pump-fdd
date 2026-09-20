import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EvidenceReferences } from "../../api";
import { tooltipStyle } from "../../lib";
import { ProtocolBadge } from "../ProtocolBadge";
import { GlassCard } from "../GlassCard";

const FACET_ORDER = ["global-mean", "knn-k1", "knn-k5", "knn-k10", "knn-k20", "poly2"];

type Props = { data?: EvidenceReferences };

export function ReferenceBenchmark({ data }: Props) {
  const points = (data?.points ?? []).filter((point) => FACET_ORDER.includes(point.facet));
  const facets = FACET_ORDER.filter((facet) => points.some((point) => point.facet === facet));
  const majority = data?.majority;
  const yValues = points.map((point) => point.accuracy);
  if (majority != null) yValues.push(majority);
  const yMin = yValues.length ? Math.max(0, Math.min(...yValues) - 0.05) : 0;
  const yMax = yValues.length ? Math.min(1, Math.max(...yValues) + 0.05) : 1;
  const ann0 = data?.annotation_dmin0;
  const ann05 = data?.annotation_dmin05;
  const [hover, setHover] = useState<string | null>(null);

  const knn1 = points.filter((point) => point.facet === "knn-k1").map((point) => point.accuracy);
  const flat = points
    .filter((point) => point.facet === "global-mean" || point.facet === "poly2")
    .map((point) => point.accuracy);
  const knnSpan = knn1.length ? Math.max(...knn1) - Math.min(...knn1) : 0;
  const flatSpan = flat.length ? Math.max(...flat) - Math.min(...flat) : 0;
  const aria = `Healthy-reference grid on LOMO NIST: kNN k=1 drops by ${(knnSpan * 100).toFixed(0)} points as dmin rises, while global-mean and poly2 stay within ${(flatSpan * 100).toFixed(0)} points.`;

  return (
    <GlassCard
      className="p-6 transition-opacity duration-200"
      data-testid="reference-benchmark"
      role="img"
      aria-label={aria}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h2 className="text-lg font-semibold">Healthy-reference grid</h2>
          <p className="text-xs text-white/60 mt-1">
            dmin is a leak guard, not a hyperparameter. kNN k=1 drops when neighbours are held out.
          </p>
        </div>
        <ProtocolBadge protocol={data?.badge} label="LOMO · NIST" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {facets.map((facet) => {
          const rows = points.filter((point) => point.facet === facet);
          const tt = groupByDmin(rows.filter((row) => row.conditioning === "TT"));
          const ttdew = groupByDmin(rows.filter((row) => row.conditioning === "TTdew"));
          const xs = Array.from(new Set([...tt.map((r) => r.dmin), ...ttdew.map((r) => r.dmin)])).sort(
            (a, b) => a - b,
          );
          const chart = xs.map((dmin) => ({
            dmin,
            TT: tt.find((row) => row.dmin === dmin)?.accuracy,
            TTdew: ttdew.find((row) => row.dmin === dmin)?.accuracy,
          }));
          const showAnn = facet === (ann0?.facet ?? "knn-k5");
          const dim = hover != null && hover !== facet;
          return (
            <div
              key={facet}
              className={`rounded-2xl border border-white/10 p-3 transition-opacity duration-150 ${dim ? "opacity-60" : ""} ${hover === facet ? "ring-1 ring-white/25" : ""}`}
              onMouseEnter={() => setHover(facet)}
              onMouseLeave={() => setHover(null)}
            >
              <div className="text-xs text-white/60 mb-2">{facet}</div>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="dmin" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }} />
                    <YAxis
                      domain={[yMin, yMax]}
                      tickFormatter={(value: number) => value.toFixed(2)}
                      width={30}
                      tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10 }}
                    />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => Number(value).toFixed(3)} />
                    {majority != null ? (
                      <ReferenceLine y={majority} stroke="rgba(255,255,255,0.35)" strokeDasharray="4 4" />
                    ) : null}
                    <Line type="monotone" dataKey="TT" stroke="#A78BFA" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                    <Line
                      type="monotone"
                      dataKey="TTdew"
                      stroke="#2DD4BF"
                      strokeWidth={2}
                      strokeDasharray="5 3"
                      dot={{ r: 2 }}
                      connectNulls
                    />
                    {showAnn && ann0 ? (
                      <ReferenceDot x={ann0.dmin} y={ann0.accuracy} r={4} fill="#F5C542" stroke="none" />
                    ) : null}
                    {showAnn && ann05 ? (
                      <ReferenceDot x={ann05.dmin} y={ann05.accuracy} r={4} fill="#F5C542" stroke="none" />
                    ) : null}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {showAnn && ann0 && ann05 ? (
                <p className="text-[11px] text-white/60 mt-2">
                  kNN k=5 · TT · dmin {ann0.dmin}: {ann0.accuracy.toFixed(3)} → dmin {ann05.dmin}:{" "}
                  {ann05.accuracy.toFixed(3)}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="flex gap-4 text-[11px] text-white/60 mt-3">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-4 rounded-full bg-[#A78BFA]" /> TT
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-4 border-t border-dashed border-[#2DD4BF]" /> TTdew
        </span>
        <span>dotted = majority class</span>
      </div>
    </GlassCard>
  );
}

function groupByDmin(rows: Array<{ dmin: number; accuracy: number }>) {
  const byDmin = new Map<number, number>();
  for (const row of rows) byDmin.set(row.dmin, row.accuracy);
  return Array.from(byDmin.entries()).map(([dmin, accuracy]) => ({ dmin, accuracy }));
}
