type Props = {
  T_evap: number;
  T_cond: number;
  P_evap: number;
  P_cond: number;
  superheat: number;
  subcooling: number;
  COP: number;
  fault: string;
};

export function CycleSchematic({
  T_evap,
  T_cond,
  P_evap,
  P_cond,
  superheat,
  subcooling,
  COP,
  fault,
}: Props) {
  const healthy = fault === "Normal";
  const condenserFill = fault === "Condenser_Fouling" || fault === "Condenser_Fan_Fault" ? "#F59E0B" : "#4ECDC4";
  const evaporatorFill = fault === "Evaporator_Fouling" ? "#F59E0B" : "#96CEB4";
  const compressorFill = fault === "Refrigerant_Undercharge" ? "#F59E0B" : "#FF6B6B";
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-4 items-center">
      <svg viewBox="0 0 640 360" className="w-full h-auto">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="rgba(255,255,255,0.7)" />
          </marker>
        </defs>
        <rect x="210" y="36" width="170" height="64" rx="14" fill={condenserFill} />
        <text x="295" y="74" textAnchor="middle" fill="#0b1220" fontSize="14" fontWeight="600">
          Condenser
        </text>
        <rect x="430" y="120" width="150" height="72" rx="14" fill={compressorFill} />
        <text x="505" y="162" textAnchor="middle" fill="#fff" fontSize="14" fontWeight="600">
          Compressor
        </text>
        <rect x="70" y="150" width="120" height="56" rx="14" fill="#45B7D1" />
        <text x="130" y="184" textAnchor="middle" fill="#0b1220" fontSize="13" fontWeight="600">
          Expansion
        </text>
        <rect x="210" y="250" width="170" height="64" rx="14" fill={evaporatorFill} />
        <text x="295" y="288" textAnchor="middle" fill="#0b1220" fontSize="14" fontWeight="600">
          Evaporator
        </text>
        <path d="M380 68 H505 V120" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="3" markerEnd="url(#arrow)" />
        <path d="M430 192 H295 V250" fill="none" stroke="rgba(255,107,107,0.8)" strokeWidth="3" markerEnd="url(#arrow)" />
        <path d="M210 282 H130 V206" fill="none" stroke="rgba(150,206,180,0.9)" strokeWidth="3" markerEnd="url(#arrow)" />
        <path d="M130 150 V68 H210" fill="none" stroke="rgba(69,183,209,0.9)" strokeWidth="3" markerEnd="url(#arrow)" />
        <text x="505" y="110" textAnchor="middle" fill="rgba(255,255,255,0.55)" fontSize="11">
          2  HP vapour
        </text>
        <text x="360" y="238" fill="rgba(255,255,255,0.55)" fontSize="11">
          1  suction
        </text>
        <text x="80" y="248" fill="rgba(255,255,255,0.55)" fontSize="11">
          4  LP mix
        </text>
        <text x="80" y="50" fill="rgba(255,255,255,0.55)" fontSize="11">
          3  liquid
        </text>
        <text x="295" y="118" textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="11">
          {T_cond.toFixed(1)} °C · {P_cond.toFixed(1)} bar
        </text>
        <text x="295" y="332" textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="11">
          {T_evap.toFixed(1)} °C · {P_evap.toFixed(1)} bar
        </text>
      </svg>
      <div className="glass p-4 text-sm space-y-2">
        <div className="text-[11px] uppercase tracking-wide text-white/45">Current point</div>
        <div>T_evap {T_evap.toFixed(1)} °C · {P_evap.toFixed(2)} bar</div>
        <div>T_cond {T_cond.toFixed(1)} °C · {P_cond.toFixed(2)} bar</div>
        <div>SH {superheat.toFixed(1)} K · SC {subcooling.toFixed(1)} K</div>
        <div className="text-lg font-semibold">COP {COP.toFixed(2)}</div>
        <div className={healthy ? "text-emerald-300" : "text-amber-300"}>{fault.replace(/_/g, " ")}</div>
      </div>
    </div>
  );
}
