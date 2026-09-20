import {
  Activity,
  BarChart3,
  BookOpen,
  Flame,
  FlaskConical,
  LayoutDashboard,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";

type NavItem = {
  id: string;
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
};

const items: NavItem[] = [
  { id: "insights", to: "/", icon: LayoutDashboard, label: "Insights", end: true },
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
const idle =
  `h-11 w-11 rounded-2xl grid place-items-center text-white/70 hover:text-white hover:bg-white/10 transition-colors duration-150 ${focusRing}`;
const on =
  `h-11 w-11 rounded-2xl grid place-items-center bg-white text-slate-900 shadow-[0_8px_20px_rgba(255,255,255,0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/40`;

export function Sidebar({ active }: Props) {
  return (
    <aside className="glass-pill sticky top-4 sm:top-10 flex flex-row sm:flex-col items-center gap-3 sm:gap-4 px-2.5 py-3 sm:py-5 h-fit w-full sm:w-auto justify-center">
      <div className="h-10 w-10 rounded-full bg-white text-slate-900 grid place-items-center text-xs font-bold shrink-0">
        HP
      </div>
      <nav className="flex flex-row sm:flex-col gap-1.5" aria-label="Primary">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.id}
              to={item.to}
              end={item.end === true}
              title={item.label}
              aria-label={item.label}
              aria-current={active === item.id ? "page" : undefined}
              className={({ isActive }) => (isActive || active === item.id ? on : idle)}
            >
              {({ isActive }) => (
                <Icon size={18} strokeWidth={isActive || active === item.id ? 2.2 : 1.7} />
              )}
            </NavLink>
          );
        })}
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          title="API docs"
          aria-label="API docs"
          className={idle}
        >
          <BookOpen size={18} strokeWidth={1.7} />
        </a>
      </nav>
    </aside>
  );
}
