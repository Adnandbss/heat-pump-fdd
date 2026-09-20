import type { ReactNode } from "react";
import { tooltipStyle } from "../lib";

type Props = {
  children: ReactNode;
};

export function ChartTip({ children }: Props) {
  return (
    <div
      className="pointer-events-none absolute z-20 px-2.5 py-1.5 text-[11px] leading-snug whitespace-nowrap"
      style={tooltipStyle}
    >
      {children}
    </div>
  );
}
