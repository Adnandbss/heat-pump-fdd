export const CLASS_COLORS = ["#7DFF7A", "#5B9DFF", "#F5C542", "#7EC8FF", "#F472B6", "#FB923C"];

export const FAULT_COLORS: Record<string, string> = {
  Normal: "#7DFF7A",
  Condenser_Fouling: "#5B9DFF",
  Evaporator_Fouling: "#7EC8FF",
  Refrigerant_Undercharge: "#F5C542",
  Condenser_Fan_Fault: "#FB923C",
  Evaporator_Fan_Fault: "#F472B6",
};

export function pretty(name: string) {
  return name.replace(/_/g, " ");
}

export function colorFor(name: string, index = 0) {
  return FAULT_COLORS[name] ?? CLASS_COLORS[index % CLASS_COLORS.length];
}

export const tooltipStyle = {
  background: "rgba(20, 20, 28, 0.72)",
  backdropFilter: "blur(14px)",
  border: "1px solid rgba(255,255,255,0.16)",
  borderRadius: 14,
  color: "#F8F8FC",
};

export const PAGE_COPY: Record<string, { eyebrow: string; title: string; subtitle: string }> = {
  insights: {
    eyebrow: "Overview",
    title: "HeatPump FDD",
    subtitle: "CoolProp R410A cycle · calibrated Gradient Boosting",
  },
  live: {
    eyebrow: "Live FDD",
    title: "Fault injection",
    subtitle: "Watch the model relabel each timestep after the fault is injected",
  },
  diagnose: {
    eyebrow: "Diagnosis",
    title: "Live diagnosis",
    subtitle: "Simulate an operating point and read class probabilities",
  },
  models: {
    eyebrow: "Models",
    title: "Hold-out performance",
    subtitle: "Synthetic 5000-cycle set · 23 residual features",
  },
  thermo: {
    eyebrow: "Thermodynamics",
    title: "R410A cycle",
    subtitle: "P-h diagram, compressor envelope and COP curves",
  },
};
