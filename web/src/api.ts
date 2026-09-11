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

export function fetchStats(faultType = "Condenser_Fouling") {
  return request<Stats>(`/api/stats?fault_type=${encodeURIComponent(faultType)}`);
}

export function fetchOverview() {
  return request<Overview>("/api/overview");
}

export function fetchActivity() {
  return request<Activity>("/api/activity");
}

export function fetchChallenges() {
  return request<{ challenges: Challenge[] }>("/api/challenges");
}

export function fetchCatalog() {
  return request<Catalog>("/api/catalog");
}

export function fetchModels() {
  return request<ModelsPayload>("/api/models");
}

export function fetchDataset() {
  return request<DatasetPayload>("/api/dataset");
}

export function fetchDistribution(feature: string) {
  return request<{ feature: string; boxes: BoxStats[] }>(
    `/api/explore/distribution?feature=${encodeURIComponent(feature)}`,
  );
}

export function fetchScatter(x: string, y: string) {
  return request<{ x: string; y: string; points: ScatterPoint[] }>(
    `/api/explore/scatter?x=${encodeURIComponent(x)}&y=${encodeURIComponent(y)}`,
  );
}

export function fetchAdvanced() {
  return request<{ labels: string[]; matrix: number[][] }>("/api/advanced");
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

export function fetchPh(params: {
  T_evap: number;
  T_cond: number;
  superheat: number;
  subcooling: number;
}) {
  const query = new URLSearchParams({
    T_evap: String(params.T_evap),
    T_cond: String(params.T_cond),
    superheat: String(params.superheat),
    subcooling: String(params.subcooling),
  });
  return request<PhPayload>(`/api/thermo/ph?${query.toString()}`);
}

export function fetchPhCompare(params: {
  T_evap: number;
  T_cond: number;
  superheat: number;
  subcooling: number;
  load_factor: number;
  t_source: number;
  scenario: "nominal" | "condenser" | "evaporator" | "all";
}) {
  const query = new URLSearchParams({
    T_evap: String(params.T_evap),
    T_cond: String(params.T_cond),
    superheat: String(params.superheat),
    subcooling: String(params.subcooling),
    load_factor: String(params.load_factor),
    t_source: String(params.t_source),
    scenario: params.scenario,
  });
  return request<PhComparePayload>(`/api/thermo/ph/compare?${query.toString()}`);
}

export function fetchCopCurves() {
  return request<{
    curves: Array<{ T_amb: number; carnot: number; estimated: number }>;
    measured: Array<{ T_amb: number; COP: number }>;
  }>("/api/thermo/cop");
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

export function fetchCondenserSweep(T_evap: number, loadMin: number, loadMax: number) {
  const query = new URLSearchParams({
    T_evap: String(T_evap),
    load_min: String(loadMin),
    load_max: String(loadMax),
  });
  return request<SweepPayload>(`/api/thermo/sweep/condenser?${query.toString()}`);
}

export function fetchEvaporatorSweep(T_cond: number, sourceMin: number, sourceMax: number) {
  const query = new URLSearchParams({
    T_cond: String(T_cond),
    source_min: String(sourceMin),
    source_max: String(sourceMax),
  });
  return request<SweepPayload>(`/api/thermo/sweep/evaporator?${query.toString()}`);
}

export function fetchAshrae() {
  return request<{ coolprop: boolean; rows: Array<{ T: number; ashrae: number; coolprop: number; error_pct: number }> }>(
    "/api/thermo/ashrae",
  );
}

export function fetchAmbientHeatmap() {
  return request<{ x_labels: string[]; y_labels: string[]; matrix: number[][] }>("/api/advanced/ambient");
}

export function postSimulate(body: {
  T_source: number;
  T_sink: number;
  speed_ratio: number;
  fault_type: string;
}) {
  return request<Diagnosis>("/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function postPredict(features: Record<string, number>) {
  return request<{ label: string; confidence: number; probabilities: Record<string, number> }>(
    "/predict",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ features }),
    },
  );
}

export function postLive(body: {
  fault_type: string;
  inject_at: number;
  n_points: number;
}) {
  return request<{ trace: ActivityPoint[] }>("/live", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
