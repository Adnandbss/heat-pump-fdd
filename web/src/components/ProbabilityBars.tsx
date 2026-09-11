import { pretty } from "../lib";
import type { Diagnosis } from "../api";

type Props = {
  payload?: Diagnosis;
  manual?: { label: string; confidence: number; probabilities: Record<string, number> };
};

export function ProbabilityBars({ payload, manual }: Props) {
  const probabilities = manual?.probabilities ?? payload?.diagnosis.probabilities ?? {};
  const rows = Object.entries(probabilities).sort((a, b) => a[1] - b[1]);
  if (rows.length === 0) {
    return <div className="text-sm text-white/40">No probabilities yet.</div>;
  }
  return (
    <ul className="space-y-2">
      {rows.map(([name, value]) => (
        <li key={name}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-white/70">{pretty(name)}</span>
            <span className="tabular-nums text-white/45">{(value * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full bg-white/8 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-400"
              style={{ width: `${Math.max(value * 100, 1.5)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
