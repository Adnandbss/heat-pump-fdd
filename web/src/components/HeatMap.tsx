import { useState } from "react";
import { pretty } from "../lib";
import { ChartTip } from "./ChartTip";

type Props = {
  labels: string[];
  rowLabels?: string[];
  matrix: number[][];
  percent?: boolean;
  integers?: boolean;
  gap?: number;
};

function cellColor(value: number) {
  const t = Math.max(0, Math.min(1, value));
  return `rgba(91, 157, 255, ${0.08 + t * 0.82})`;
}

export function HeatMap({
  labels,
  rowLabels,
  matrix,
  percent = true,
  integers = false,
  gap = 4,
}: Props) {
  const rows = rowLabels ?? labels;
  const maxAbs = Math.max(
    1,
    ...matrix.flatMap((row) => row.map((value) => Math.abs(value))),
  );
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="overflow-x-auto relative">
      <table className="w-full text-[10px] border-separate" style={{ borderSpacing: gap }}>
        <thead>
          <tr>
            <th />
            {labels.map((label) => (
              <th key={label} scope="col" className="font-medium text-white/60 px-1 pb-1 text-center max-w-[72px]">
                {pretty(label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((rowLabel, row) => (
            <tr key={rowLabel}>
              <th scope="row" className="text-left font-medium text-white/60 pr-2 whitespace-nowrap">
                {pretty(rowLabel)}
              </th>
              {(matrix[row] ?? []).map((value, col) => {
                const intensity = percent ? value : integers ? value / maxAbs : (value + 1) / 2;
                const key = `${row}-${col}`;
                const active = hover === key;
                const dim = hover != null && !active;
                return (
                  <td
                    key={key}
                    className={`relative rounded-lg text-center tabular-nums py-3 px-1 transition-opacity duration-150 ${dim ? "opacity-60" : ""} ${active ? "ring-1 ring-white/25" : ""}`}
                    style={{ background: cellColor(intensity) }}
                    onMouseEnter={() => setHover(key)}
                    onMouseLeave={() => setHover(null)}
                  >
                    {integers ? String(value) : value.toFixed(2)}
                    {active ? (
                      <ChartTip>
                        {pretty(rowLabel)} → {pretty(labels[col])}: {integers ? String(value) : value.toFixed(3)}
                      </ChartTip>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
