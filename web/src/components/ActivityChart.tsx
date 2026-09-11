import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { GlassCard } from "./GlassCard";
import type { Activity } from "../api";

type Props = {
  data?: Activity;
};

export function ActivityChart({ data }: Props) {
  const injectAt = data?.inject_at ?? 7;
  const rows = (data?.trace ?? []).map((point) => ({
    ...point,
    fill: point.t >= injectAt ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.22)",
  }));

  return (
    <GlassCard className="p-6 h-full min-h-[280px]">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Activity</h2>
          <p className="text-xs text-white/45 mt-1">
            P_cond after {data?.fault_type ?? "Condenser_Fouling"} injection
          </p>
        </div>
        <span className="text-[11px] px-2.5 py-1 rounded-full bg-white/10 text-white/70">Live trace</span>
      </div>
      <div className="h-48">
        {rows.length === 0 ? (
          <div className="h-full grid place-items-center text-sm text-white/40">Waiting for live telemetry…</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} barSize={18} barCategoryGap={10}>
              <XAxis
                dataKey="t"
                tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                contentStyle={{
                  background: "rgba(20,20,28,0.82)",
                  backdropFilter: "blur(12px)",
                  border: "1px solid rgba(255,255,255,0.16)",
                  borderRadius: 14,
                  color: "#fff",
                }}
                formatter={(value) => [`${Number(value).toFixed(2)} bar`, "P_cond"]}
              />
              <Bar dataKey="P_cond" radius={[10, 10, 10, 10]}>
                {rows.map((row) => (
                  <Cell key={row.t} fill={row.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </GlassCard>
  );
}
