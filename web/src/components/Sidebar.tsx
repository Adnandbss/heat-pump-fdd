import {
  Activity,
  BarChart3,
  BookOpen,
  Flame,
  LayoutDashboard,
  Stethoscope,
} from "lucide-react";

const items = [
  { id: "insights", icon: LayoutDashboard, label: "Insights" },
  { id: "live", icon: Activity, label: "Live" },
  { id: "diagnose", icon: Stethoscope, label: "Diagnose" },
  { id: "models", icon: BarChart3, label: "Models" },
  { id: "thermo", icon: Flame, label: "Thermo" },
  { id: "docs", icon: BookOpen, label: "API docs", href: "/docs" },
] as const;

type Props = {
  active: string;
  onSelect: (id: string) => void;
};

export function Sidebar({ active, onSelect }: Props) {
  return (
    <aside className="glass-pill sticky top-10 flex flex-col items-center gap-4 px-2.5 py-5 h-fit">
      <div className="h-10 w-10 rounded-full bg-white text-slate-900 grid place-items-center text-xs font-bold">
        HP
      </div>
      <nav className="flex flex-col gap-1.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          const idle =
            "h-11 w-11 rounded-2xl grid place-items-center text-white/70 hover:text-white hover:bg-white/10 transition";
          const on =
            "h-11 w-11 rounded-2xl grid place-items-center bg-white text-slate-900 shadow-[0_8px_20px_rgba(255,255,255,0.18)]";
          if ("href" in item && item.href) {
            return (
              <a key={item.id} href={item.href} target="_blank" rel="noreferrer" title={item.label} className={idle}>
                <Icon size={18} strokeWidth={1.7} />
              </a>
            );
          }
          return (
            <button
              key={item.id}
              type="button"
              title={item.label}
              onClick={() => onSelect(item.id)}
              className={isActive ? on : idle}
            >
              <Icon size={18} strokeWidth={isActive ? 2.2 : 1.7} />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
