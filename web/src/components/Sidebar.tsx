import {
  Activity,
  BarChart3,
  BookOpen,
  Flame,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { API_BASE } from "../api";

type NavItem = {
  id: string;
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
};

const items: NavItem[] = [
  { id: "fleet", to: "/", icon: ListChecks, label: "Fleet triage", end: true },
  { id: "insights", to: "/insights", icon: LayoutDashboard, label: "Insights" },
  { id: "evidence", to: "/evidence", icon: FlaskConical, label: "Evidence" },
  { id: "live", to: "/live", icon: Activity, label: "Live" },
  { id: "diagnose", to: "/diagnose", icon: Stethoscope, label: "Diagnose" },
  { id: "models", to: "/models", icon: BarChart3, label: "Models" },
  { id: "thermo", to: "/thermo", icon: Flame, label: "Thermo" },
];

type Props = {
  active: string;
};

const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40";
const itemBase =
  "rounded-2xl flex items-center justify-center sm:justify-start gap-2 sm:px-3 sm:w-full transition-colors duration-150";
const idle = `${itemBase} text-white/70 hover:text-white hover:bg-white/10 ${focusRing}`;
const on =
  `${itemBase} bg-white text-slate-900 shadow-[0_8px_20px_rgba(255,255,255,0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/40`;

export function Sidebar({ active }: Props) {
  return (
    <aside className="glass-pill sticky top-4 sm:top-10 flex flex-row sm:flex-col items-center sm:items-stretch gap-3 sm:gap-4 px-2.5 py-3 sm:px-3 sm:py-5 h-fit w-full sm:w-44 justify-center">
      <div className="h-10 w-10 rounded-full bg-white text-slate-900 grid place-items-center text-xs font-bold shrink-0 sm:mx-auto">
        HP
      </div>
      <nav className="flex flex-row sm:flex-col gap-1.5 sm:w-full" aria-label="Primary">
        {items.map((item) => {
          const Icon = item.icon;
          const primary = item.id === "fleet";
          const selected = active === item.id;
          return (
            <NavLink
              key={item.id}
              to={item.to}
              end={item.end === true}
              title={item.label}
              aria-label={item.label}
              aria-current={selected ? "page" : undefined}
              className={({ isActive }) => {
                const selectedNow = isActive || selected;
                const size = primary
                  ? "h-11 w-11 sm:w-full text-sm font-medium"
                  : "h-9 w-9 sm:w-full text-xs";
                return `${selectedNow ? on : idle} ${size} ${!primary && !selectedNow ? "opacity-60" : ""}`;
              }}
            >
              {({ isActive }) => (
                <>
                  <Icon size={primary ? 18 : 15} strokeWidth={isActive || selected ? 2.2 : 1.7} />
                  <span className="hidden sm:inline">{item.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noreferrer"
          title="API docs"
          aria-label="API docs"
          className={`${idle} h-9 w-9 sm:w-full text-xs text-white/50`}
        >
          <BookOpen size={18} strokeWidth={1.7} />
          <span className="hidden sm:inline">API docs</span>
        </a>
      </nav>
    </aside>
  );
}
