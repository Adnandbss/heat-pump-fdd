import { GlassCard } from "./GlassCard";
import type { Activity } from "../api";

type Props = {
  activity?: Activity;
};

export function CalendarWidget({ activity }: Props) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const points = activity?.trace.slice(-7) ?? [];
  const injectAt = activity?.inject_at ?? 7;
  const highlight = points.findIndex((point) => point.t >= injectAt);

  return (
    <GlassCard className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Live window</h2>
        <span className="text-xs text-white/40">inject t={injectAt}</span>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          const point = points[index];
          const selected = highlight === index || (highlight < 0 && index === points.length - 1);
          return (
            <div key={day} className="text-center">
              <div className="text-[10px] uppercase tracking-wide text-white/40 mb-2">{day}</div>
              <div
                className={
                  selected
                    ? "mx-auto h-10 w-10 rounded-full bg-white text-slate-900 text-sm font-semibold grid place-items-center"
                    : "mx-auto h-10 w-10 rounded-full text-sm text-white/75 grid place-items-center"
                }
              >
                {point ? point.t : "--"}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
