import { getJson } from "./client";

export interface KpiMetric {
  current: number | null;
  previous: number | null;
  delta: number | null;
  unit: "score" | "count";
}

export interface KpisWithDeltas {
  window_days: number;
  current_window: { since: string; until: string };
  previous_window: { since: string; until: string };
  metrics: {
    avg_sentiment: KpiMetric;
    active_employees: KpiMetric;
    new_tickets: KpiMetric;
    resolved_tickets: KpiMetric;
    at_risk_count: KpiMetric;
  };
}

export async function getKpisWithDeltas(days = 7): Promise<KpisWithDeltas | null> {
  return getJson<KpisWithDeltas>(`/api/v1/analytics/kpis-with-deltas?days=${days}`);
}

export interface DepartmentHeatmapRow {
  department_id: string | null;
  department_name: string;
  total: number;
  positive: number;
  watch: number;
  at_risk: number;
  unknown: number;
  avg_sentiment: number | null;
}

export interface DepartmentHeatmap {
  departments: DepartmentHeatmapRow[];
}

export async function getDepartmentsHeatmap(): Promise<DepartmentHeatmap | null> {
  return getJson<DepartmentHeatmap>(`/api/v1/analytics/departments-heatmap`);
}
