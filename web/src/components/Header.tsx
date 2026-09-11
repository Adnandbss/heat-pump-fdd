import { Bell } from "lucide-react";
import { PAGE_COPY } from "../lib";

type Props = {
  page: string;
};

export function Header({ page }: Props) {
  const copy = PAGE_COPY[page] ?? PAGE_COPY.insights;
  return (
    <header className="flex items-center justify-between mb-7">
      <div>
        <h1 className="text-[2rem] font-semibold tracking-tight leading-none">{copy.title}</h1>
        <p className="text-sm text-white/55 mt-2">{copy.subtitle}</p>
      </div>
      <div className="flex items-center gap-3">
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="glass hidden sm:grid h-11 px-4 rounded-full place-items-center text-xs text-white/75"
        >
          API docs
        </a>
        <button
          type="button"
          className="glass h-11 w-11 rounded-full grid place-items-center text-white/80"
          aria-label="Notifications"
        >
          <Bell size={18} strokeWidth={1.7} />
        </button>
        <div className="glass flex items-center gap-3 pl-1.5 pr-4 py-1.5 rounded-full">
          <div className="h-9 w-9 rounded-full bg-gradient-to-br from-sky-300 to-indigo-400 grid place-items-center text-xs font-semibold text-slate-900">
            AA
          </div>
          <div className="leading-tight hidden sm:block">
            <div className="text-sm font-medium">Adnan Ahali</div>
            <div className="text-[11px] text-white/50">MEng · Berkeley</div>
          </div>
        </div>
      </div>
    </header>
  );
}
