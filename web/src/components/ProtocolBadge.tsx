import type { ProtocolRef } from "../api";

const PROTOCOL: Record<string, string> = {
  "holdout-test": "hold-out",
  "holdout-test-6class": "6-class hold-out",
  "leaked-dCOP": "leaked d_COP",
  "random-cv": "random CV",
  LOMO: "LOMO",
  sim2real: "sim2real",
  "majority-class": "majority",
  "holdout-domain": "domain hold-out",
};

const REFERENCE: Record<string, string> = {
  simulated: "simulated",
  "target-machine": "NIST",
  "training-machine": "transferred",
  "measured-knn5": "measured",
  none: "",
};

type Props = {
  protocol?: ProtocolRef | null;
  label?: string;
  className?: string;
};

export function ProtocolBadge({ protocol, label, className = "" }: Props) {
  const warn = protocol?.protocol === "random-cv";
  const text =
    label ??
    (protocol
      ? [PROTOCOL[protocol.protocol] ?? protocol.protocol, REFERENCE[protocol.reference] ?? protocol.reference]
          .filter(Boolean)
          .join(" · ")
      : "");
  if (!text) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-white/18 bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/70 ${className}`}
      title={protocol ? `${protocol.experiment} / ${protocol.protocol} / ${protocol.reference}` : text}
    >
      {text}
      {warn ? <span aria-label="optimistic protocol">⚠</span> : null}
    </span>
  );
}
