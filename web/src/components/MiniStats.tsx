import { Gauge, Thermometer, Wind } from "lucide-react";
import type { Stats } from "../api";

type Props = {
  stats?: Stats;
};

export function MiniStats({ stats }: Props) {
  const tiles = [
    {
      label: "COP",
      value: stats ? stats.COP.toFixed(2) : "--",
      hint: "heating efficiency",
      icon: Gauge,
    },
    {
      label: "P_cond",
      value: stats ? `${stats.P_cond.toFixed(1)}` : "--",
      hint: "bar",
      icon: Wind,
    },
    {
      label: "T_discharge",
      value: stats ? `${stats.T_discharge.toFixed(0)}` : "--",
      hint: "°C",
      icon: Thermometer,
    },
  ];

  return (
    <div className="flex flex-col gap-3 h-full">
      {tiles.map((tile) => {
        const Icon = tile.icon;
        return (
          <div key={tile.label} className="glass flex items-center gap-4 px-4 py-4 flex-1 min-h-[84px]">
            <div className="h-12 w-12 rounded-2xl bg-white/10 border border-white/15 grid place-items-center text-white/80">
              <Icon size={20} strokeWidth={1.6} />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] uppercase tracking-wide text-white/45">{tile.label}</div>
              <div className="text-2xl font-semibold leading-tight mt-0.5">{tile.value}</div>
              <div className="text-xs text-white/50">{tile.hint}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
