import type { Challenge } from "../api";
import { GlassCard } from "./GlassCard";

type Props = {
  challenges?: Challenge[];
};

export function Challenges({ challenges }: Props) {
  return (
    <GlassCard className="p-6 h-full">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold">Challenges</h2>
        <span className="text-[11px] text-white/45">
          {challenges ? `${challenges.length} scenarios` : "…"}
        </span>
      </div>
      <ul className="space-y-4">
        {!challenges ? (
          <li className="text-sm text-white/40">Loading scenarios…</li>
        ) : challenges.length === 0 ? (
          <li className="text-sm text-white/40">No injected scenarios yet.</li>
        ) : null}
        {(challenges ?? []).map((item) => (
          <li key={item.id} className="flex items-center gap-3">
            <Ring value={item.progress} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium truncate">{item.title}</div>
              <div className="text-[11px] text-white/40">
                {item.progress}% · {item.predicted.replace(/_/g, " ")}
              </div>
            </div>
            <span
              className={
                item.status === "Complete"
                  ? "shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-md bg-[#7DFF7A] text-slate-900"
                  : "shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-md bg-[#E4C04A] text-slate-900"
              }
            >
              {item.status}
            </span>
          </li>
        ))}
      </ul>
    </GlassCard>
  );
}

function Ring({ value }: { value: number }) {
  const r = 14;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.max(0, Math.min(100, value)) / 100) * c;
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" className="shrink-0 -rotate-90">
      <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
      <circle
        cx="18"
        cy="18"
        r={r}
        fill="none"
        stroke="#7DFF7A"
        strokeWidth="3"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
      />
    </svg>
  );
}
