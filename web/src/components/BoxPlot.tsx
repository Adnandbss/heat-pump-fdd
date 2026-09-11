import { colorFor, pretty } from "../lib";
import type { BoxStats } from "../api";

type Props = {
  boxes: BoxStats[];
};

export function BoxPlot({ boxes }: Props) {
  if (boxes.length === 0) {
    return <div className="h-56 grid place-items-center text-sm text-white/40">No distribution yet.</div>;
  }
  const lo = Math.min(...boxes.map((box) => box.min));
  const hi = Math.max(...boxes.map((box) => box.max));
  const span = hi - lo || 1;
  const y = (value: number) => `${((hi - value) / span) * 100}%`;
  const h = (from: number, to: number) => `${(Math.abs(to - from) / span) * 100}%`;

  return (
    <div className="h-56 flex items-end gap-2">
      {boxes.map((box, index) => (
        <div key={box.name} className="flex-1 h-full flex flex-col items-center min-w-0">
          <div className="relative flex-1 w-full">
            <div
              className="absolute left-1/2 w-px bg-white/25"
              style={{
                top: y(box.max),
                height: h(box.min, box.max),
              }}
            />
            <div
              className="absolute left-1/2 -translate-x-1/2 w-3 h-px bg-white/50"
              style={{ top: y(box.max) }}
            />
            <div
              className="absolute left-1/2 -translate-x-1/2 w-3 h-px bg-white/50"
              style={{ top: y(box.min) }}
            />
            <div
              className="absolute left-1/2 -translate-x-1/2 w-7 rounded-md border border-white/20"
              style={{
                top: y(box.q3),
                height: h(box.q1, box.q3),
                background: `${colorFor(box.name, index)}55`,
              }}
            />
            <div
              className="absolute left-1/2 -translate-x-1/2 w-7 h-0.5"
              style={{ top: y(box.median), background: colorFor(box.name, index) }}
            />
          </div>
          <div className="text-[10px] text-white/45 mt-2 truncate w-full text-center">
            {pretty(box.name).split(" ")[0]}
          </div>
        </div>
      ))}
    </div>
  );
}
