import { GlassCard } from "./GlassCard";
import type { Stats } from "../api";

type Props = {
  stats?: Stats;
};

export function OutputWidget({ stats }: Props) {
  const healthy = stats?.label === "Normal";
  return (
    <GlassCard className="p-6 flex flex-col justify-between min-h-[150px]">
      <div className="flex items-start justify-between">
        <p className="text-xs uppercase tracking-wide text-white/45">Latest output</p>
        <span
          className={
            healthy
              ? "text-[11px] font-semibold px-2.5 py-1 rounded-md bg-[#7DFF7A] text-slate-900"
              : "text-[11px] font-semibold px-2.5 py-1 rounded-md bg-[#E4C04A] text-slate-900"
          }
        >
          {healthy ? "amazing!" : "fault found"}
        </span>
      </div>
      <div>
        <div className="text-2xl font-semibold leading-tight">
          {stats?.label.replace(/_/g, " ") ?? "—"}
        </div>
        <p className="text-sm text-white/50 mt-1">
          {stats ? `${(stats.confidence * 100).toFixed(1)}% confidence` : "waiting for API"}
        </p>
      </div>
    </GlassCard>
  );
}
