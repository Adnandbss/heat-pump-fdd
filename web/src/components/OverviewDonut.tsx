import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { GlassCard } from "./GlassCard";
import type { Overview, Stats } from "../api";

const COLORS = ["#7DFF7A", "#5B9DFF", "#F5C542", "#7EC8FF", "#F472B6", "#FB923C"];

type Props = {
  overview?: Overview;
  stats?: Stats;
};

export function OverviewDonut({ overview, stats }: Props) {
  const slices = overview?.classes ?? [];
  const confidence = stats ? Math.round(stats.confidence * 100) : 0;

  return (
    <GlassCard className="p-6 h-full">
      <h2 className="text-lg font-semibold mb-1">Overview</h2>
      <p className="text-xs text-white/45 mb-4">Class mix on the synthetic set</p>
      <div className="flex items-center gap-4">
        <div className="relative w-36 h-36 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="name"
                innerRadius={42}
                outerRadius={62}
                paddingAngle={3}
                stroke="none"
              >
                {slices.map((row, index) => (
                  <Cell key={row.name} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 grid place-items-center pointer-events-none">
            <div className="text-center">
              <div className="text-xl font-semibold">{confidence}%</div>
              <div className="text-[10px] text-white/40 uppercase">confidence</div>
            </div>
          </div>
        </div>
        <ul className="space-y-2 text-xs flex-1 min-w-0">
          {slices.length === 0 ? (
            <li className="text-white/40">No class mix yet.</li>
          ) : null}
          {slices.slice(0, 6).map((row, index) => (
            <li key={row.name} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 truncate text-white/70">
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ background: COLORS[index % COLORS.length] }}
                />
                {row.name.replace(/_/g, " ")}
              </span>
              <span className="text-white/45">{Math.round(row.share * 100)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </GlassCard>
  );
}
