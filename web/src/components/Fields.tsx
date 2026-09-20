type SliderProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  digits?: number;
  onChange: (value: number) => void;
};

export function SliderField({
  label,
  value,
  min,
  max,
  step = 1,
  suffix = "",
  digits = 1,
  onChange,
}: SliderProps) {
  const shown = Number.isInteger(step) && step >= 1 ? String(value) : value.toFixed(digits);
  return (
    <label className="block">
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-white/50">{label}</span>
        <span className="tabular-nums">
          {shown}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-sky-300"
      />
    </label>
  );
}

type SelectProps = {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
};

export function SelectField({ label, value, options, onChange }: SelectProps) {
  return (
    <label className="block">
      <div className="text-xs text-white/50 mb-1.5">{label}</div>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl bg-white/10 border border-white/20 px-3 py-2.5 text-sm text-white outline-none transition-colors duration-150"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} className="bg-slate-900">
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
