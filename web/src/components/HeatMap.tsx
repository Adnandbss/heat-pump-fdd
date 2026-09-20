import { pretty } from "../lib";

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
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px] border-separate" style={{ borderSpacing: gap }}>
        <thead>
          <tr>
            <th />
            {labels.map((label) => (
              <th key={label} className="font-medium text-white/40 px-1 pb-1 text-center max-w-[72px]">
                {pretty(label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((rowLabel, row) => (
            <tr key={rowLabel}>
              <th className="text-left font-medium text-white/40 pr-2 whitespace-nowrap">
                {pretty(rowLabel)}
              </th>
              {(matrix[row] ?? []).map((value, col) => {
                const intensity = percent ? value : integers ? value / maxAbs : (value + 1) / 2;
                return (
                  <td
                    key={`${row}-${col}`}
                    className="rounded-lg text-center tabular-nums py-2 px-1"
                    style={{ background: cellColor(intensity) }}
                  >
                    {integers ? String(value) : value.toFixed(2)}
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
