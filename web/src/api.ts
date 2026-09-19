import type { components } from "./api.generated";

export const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type Stats = {
  fault_type: string;
  label: string;
  confidence: number;
  probabilities: Record<string, number>;
  COP: number;
  P_cond: number;
  P_evap: number;
  T_discharge: number;
  superheat: number;
  subcooling: number;
  model: string;
};

export type OverviewClass = {
  name: string;
  value: number;
  share: number;
};

export type Overview = {
  total: number;
  classes: OverviewClass[];
  f1?: number;
  accuracy?: number;
};

export type ActivityPoint = {
  t: number;
  P_cond: number;
  P_evap?: number;
  COP: number;
  predicted: string;
  confidence: number;
  injected_fault?: string;
  severity?: number;
  T_discharge?: number;
  superheat?: number;
  subcooling?: number;
};

export type Activity = {
  fault_type: string;
  inject_at: number;
  trace: ActivityPoint[];
};

export type Challenge = {
  id: string;
  title: string;
  description: string;
  injected: string;
  predicted: string;
  confidence: number;
  status: "On Going" | "Complete";
  progress: number;
};

export type Scenario = {
  title: string;
  fault_type: string;
  params: Record<string, number>;
  description: string;
};

export type Catalog = {
  classes: string[];
  features: string[];
  faults: string[];
  scenarios: Scenario[];
  model: {
    name: string;
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1?: number;
    f1_per_class?: Record<string, number>;
    n_samples?: number;
    n_features?: number;
    calibrated?: boolean;
    coolprop?: boolean;
  };
};

export type ModelsPayload = {
  metadata: Record<string, unknown>;
  comparison: Array<Record<string, string | number>>;
  confusion: { labels: string[]; matrix: number[][] };
  importance: Array<{ feature: string; importance: number }>;
  f1_per_class: Array<{ name: string; f1: number }>;
};

export type DatasetPayload = {
  n_samples: number;
  n_classes: number;
  normal_share: number;
  counts: Record<string, number>;
  describe: Record<string, { mean: number; std: number; min: number; max: number }>;
  columns: string[];
};

export type BoxStats = {
  name: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean: number;
};

export type ScatterPoint = { x: number; y: number; fault_type: string };

export type Diagnosis = {
  conditions: Record<string, number | string>;
  cycle: {
    P_evap: number;
    P_cond: number;
    T_evap: number;
    T_cond: number;
    T_suction: number;
    T_discharge: number;
    superheat: number;
    subcooling: number;
    compression_ratio: number;
    W_comp: number;
    Q_cond: number;
    COP: number;
  };
  features: Record<string, number>;
  diagnosis: {
    label: string;
    confidence: number;
    probabilities: Record<string, number>;
  };
};

export type PhPayload = {
  coolprop: boolean;
  P_evap: number;
  P_cond: number;
  COP: number;
  saturation: Array<{ T: number; P: number; h_liq: number; h_vap: number }>;
  cycle: Array<{ name: string; h: number; P: number }>;
  envelope: {
    normal: { T_evap: number[]; T_cond: number[] };
    extended: { T_evap: number[]; T_cond: number[] };
  };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new Error(`${path} failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function isAbortError(err: unknown) {
  return (
    (typeof DOMException !== "undefined" && err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  );
}

export function fetchStats(faultType = "Condenser_Fouling", signal?: AbortSignal) {
  return request<Stats>(`/api/stats?fault_type=${encodeURIComponent(faultType)}`, { signal });
}

export function fetchOverview(signal?: AbortSignal) {
  return request<Overview>("/api/overview", { signal });
}

export function fetchActivity(signal?: AbortSignal) {
  return request<Activity>("/api/activity", { signal });
}

export function fetchChallenges(signal?: AbortSignal) {
  return request<{ challenges: Challenge[] }>("/api/challenges", { signal });
}

export function fetchCatalog(signal?: AbortSignal) {
  return request<Catalog>("/api/catalog", { signal });
}

export function fetchModels(signal?: AbortSignal) {
  return request<ModelsPayload>("/api/models", { signal });
}

export function fetchDataset(signal?: AbortSignal) {
  return request<DatasetPayload>("/api/dataset", { signal });
}

export function fetchDistribution(feature: string, signal?: AbortSignal) {
  return request<{ feature: string; boxes: BoxStats[] }>(
    `/api/explore/distribution?feature=${encodeURIComponent(feature)}`,
    { signal },
  );
}

export function fetchScatter(x: string, y: string, signal?: AbortSignal) {
  return request<{ x: string; y: string; points: ScatterPoint[] }>(
    `/api/explore/scatter?x=${encodeURIComponent(x)}&y=${encodeURIComponent(y)}`,
    { signal },
  );
}

export function fetchAdvanced(signal?: AbortSignal) {
  return request<{ labels: string[]; matrix: number[][] }>("/api/advanced", { signal });
}

export type PhOverlay = {
  T_evap: number;
  T_cond: number;
  P_evap: number;
  P_cond: number;
  COP: number;
  cycle: Array<{ name: string; h: number; P: number }>;
};

export type PhComparePayload = {
  coolprop: boolean;
  scenario: string;
  saturation: Array<{ T: number; P: number; h_liq: number; h_vap: number }>;
  nominal: PhOverlay;
  condenser: PhOverlay | null;
  evaporator: PhOverlay | null;
};

export function fetchPh(
  params: {
    T_evap: number;
    T_cond: number;
    superheat: number;
    subcooling: number;
  },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    T_evap: String(params.T_evap),
    T_cond: String(params.T_cond),
    superheat: String(params.superheat),
    subcooling: String(params.subcooling),
  });
  return request<PhPayload>(`/api/thermo/ph?${query.toString()}`, { signal });
}

export function fetchPhCompare(
  params: {
    T_evap: number;
    T_cond: number;
    superheat: number;
    subcooling: number;
    load_factor: number;
    t_source: number;
    scenario: "nominal" | "condenser" | "evaporator" | "all";
  },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    T_evap: String(params.T_evap),
    T_cond: String(params.T_cond),
    superheat: String(params.superheat),
    subcooling: String(params.subcooling),
    load_factor: String(params.load_factor),
    t_source: String(params.t_source),
    scenario: params.scenario,
  });
  return request<PhComparePayload>(`/api/thermo/ph/compare?${query.toString()}`, { signal });
}

export function fetchCopCurves(signal?: AbortSignal) {
  return request<{
    curves: Array<{ T_amb: number; carnot: number; estimated: number }>;
    measured: Array<{ T_amb: number; COP: number }>;
  }>("/api/thermo/cop", { signal });
}

export type SweepPoint = {
  T_evap: number;
  T_cond: number;
  P_evap: number;
  P_cond: number;
  tau: number;
  COP: number;
  W_comp: number;
  Q_cond: number;
  Q_evap: number;
  T_dis: number;
  load?: number;
  t_source?: number;
};

export type SweepPayload = {
  kind: string;
  coolprop: boolean;
  points: SweepPoint[];
  deltas: Record<string, number>;
  headline: string;
};

export function fetchCondenserSweep(
  T_evap: number,
  loadMin: number,
  loadMax: number,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    T_evap: String(T_evap),
    load_min: String(loadMin),
    load_max: String(loadMax),
  });
  return request<SweepPayload>(`/api/thermo/sweep/condenser?${query.toString()}`, { signal });
}

export function fetchEvaporatorSweep(
  T_cond: number,
  sourceMin: number,
  sourceMax: number,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    T_cond: String(T_cond),
    source_min: String(sourceMin),
    source_max: String(sourceMax),
  });
  return request<SweepPayload>(`/api/thermo/sweep/evaporator?${query.toString()}`, { signal });
}

export function fetchAshrae(signal?: AbortSignal) {
  return request<{ coolprop: boolean; rows: Array<{ T: number; ashrae: number; coolprop: number; error_pct: number }> }>(
    "/api/thermo/ashrae",
    { signal },
  );
}

export function fetchAmbientHeatmap(signal?: AbortSignal) {
  return request<{ x_labels: string[]; y_labels: string[]; matrix: number[][] }>("/api/advanced/ambient", {
    signal,
  });
}

export function postSimulate(
  body: {
    T_source: number;
    T_sink: number;
    speed_ratio: number;
    fault_type: string;
  },
  signal?: AbortSignal,
) {
  return request<Diagnosis>("/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function postPredict(features: Record<string, number>, signal?: AbortSignal) {
  return request<{ label: string; confidence: number; probabilities: Record<string, number> }>("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
    signal,
  });
}

export function postLive(
  body: {
    fault_type: string;
    inject_at: number;
    n_points: number;
  },
  signal?: AbortSignal,
) {
  return request<{ trace: ActivityPoint[] }>("/live", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export type ProtocolRef = components["schemas"]["ProtocolRef"];
export type SummaryCard = components["schemas"]["SummaryCard"];
export type EvidenceSummary = components["schemas"]["EvidenceSummary"];
export type LadderRung = components["schemas"]["LadderRung"];
export type EvidenceLadder = components["schemas"]["EvidenceLadder"];
export type ProtocolSlopePoint = components["schemas"]["ProtocolSlopePoint"];
export type EvidenceProtocols = components["schemas"]["EvidenceProtocols"];
export type ReferencePoint = components["schemas"]["ReferencePoint"];
export type EvidenceReferences = components["schemas"]["EvidenceReferences"];
export type PerClassScores = components["schemas"]["PerClassScores"];
export type EvidencePerClass = components["schemas"]["EvidencePerClass"];
export type RunRow = components["schemas"]["RunRow"];
export type EvidenceRuns = components["schemas"]["EvidenceRuns"];
export type EvidenceConfusion = components["schemas"]["EvidenceConfusion"];

export function fetchEvidenceSummary(signal?: AbortSignal) {
  return request<EvidenceSummary>("/api/evidence/summary", { signal });
}

export function fetchEvidenceLadder(signal?: AbortSignal) {
  return request<EvidenceLadder>("/api/evidence/ladder", { signal });
}

export function fetchEvidenceProtocols(signal?: AbortSignal) {
  return request<EvidenceProtocols>("/api/evidence/protocols", { signal });
}

export function fetchEvidenceReferences(signal?: AbortSignal) {
  return request<EvidenceReferences>("/api/evidence/references", { signal });
}

export function fetchEvidencePerClass(signal?: AbortSignal) {
  return request<EvidencePerClass>("/api/evidence/per-class", { signal });
}

export function fetchEvidenceRuns(
  params: {
    experiment?: string;
    protocol?: string;
    model?: string;
    label?: string;
    offset?: number;
    limit?: number;
  } = {},
  signal?: AbortSignal,
) {
  const query = new URLSearchParams();
  if (params.experiment) query.set("experiment", params.experiment);
  if (params.protocol) query.set("protocol", params.protocol);
  if (params.model) query.set("model", params.model);
  if (params.label) query.set("label", params.label);
  if (params.offset != null) query.set("offset", String(params.offset));
  if (params.limit != null) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<EvidenceRuns>(`/api/evidence/runs${suffix}`, { signal });
}

export function fetchEvidenceConfusion(protocol = "holdout-test", signal?: AbortSignal) {
  return request<EvidenceConfusion>(
    `/api/evidence/confusion?protocol=${encodeURIComponent(protocol)}`,
    { signal },
  );
}
