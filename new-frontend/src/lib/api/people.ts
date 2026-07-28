import type { Employee } from "@/lib/domain-types";
import { getJson, patchJson, postJson } from "@/lib/api/client";

export interface ProfileUpdatePayload {
  name?: string;
  designation?: string;
}

export interface AdminUserUpdatePayload {
  name?: string;
  email?: string;
  designation?: string;
  department_id?: string;
  manager_id?: string;
  role?: string;
  status?: string;
}

export async function updateMyProfile(payload: ProfileUpdatePayload): Promise<boolean> {
  const row = await patchJson<Record<string, unknown>>("/api/v1/users/me", payload);
  return Boolean(row);
}

export async function adminUpdateUser(userId: string, payload: AdminUserUpdatePayload): Promise<boolean> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/users/${userId}`, payload);
  return Boolean(row);
}

export interface InviteUserPayload {
  name: string;
  email: string;
  role?: string;
  designation?: string;
  department_id?: string;
  manager_id?: string;
}

export interface InviteUserResult {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  status: string;
  temp_password: string;
  invite_email_sent: boolean;
}

export async function inviteUser(payload: InviteUserPayload): Promise<InviteUserResult | null> {
  return postJson<InviteUserResult>("/api/v1/users", payload);
}

function sentimentLabelFromScore(score: number): Employee["sentiment"] {
  if (score >= 75) return "positive";
  if (score >= 55) return "neutral";
  if (score >= 35) return "watch";
  return "at_risk";
}

function initialsForName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "NA";
  const first = parts[0]?.[0] || "";
  const second = parts[1]?.[0] || "";
  return `${first}${second}`.toUpperCase();
}

type AnalyticsAugment = {
  risk: number;
  sentiment: number;
  trend: "up" | "down" | "stable";
  delta: number;
  riskLabel: "Low" | "Medium" | "High";
  narrative?: string[];
  spikeAlert: boolean;
  silentRisk: boolean;
  topTopic?: string;
  topEmotion?: string;
  complaints5d: number;
  shortTermTrend?: number;
  longTermTrend?: number;
  riskTopFactors?: string[];
  riskConfidenceBand?: string;
  sentimentLastUpdatedAt?: string;
};

function analyticsAugmentFromRow(row: Record<string, unknown>): AnalyticsAugment {
  const narrative = Array.isArray(row.narrative) ? row.narrative.map(String) : undefined;
  return {
    risk: Number(row.risk_score ?? 0),
    sentiment: Number(row.sentiment_score ?? 50),
    trend: String(row.trend ?? "stable") === "up" ? "up" : String(row.trend ?? "stable") === "down" ? "down" : "stable",
    delta: Number(row.delta ?? 0),
    riskLabel:
      String(row.risk_label ?? "Low") === "High"
        ? "High"
        : String(row.risk_label ?? "Low") === "Medium"
          ? "Medium"
          : "Low",
    narrative: narrative?.length ? narrative : undefined,
    spikeAlert: Boolean(row.spike_alert),
    silentRisk: Boolean(row.silent_risk),
    topTopic: row.top_topic ? String(row.top_topic) : undefined,
    topEmotion: row.top_emotion ? String(row.top_emotion) : undefined,
    complaints5d: Number(row.complaints_5d ?? 0),
    shortTermTrend: row.short_term_trend != null ? Number(row.short_term_trend) : undefined,
    longTermTrend: row.long_term_trend != null ? Number(row.long_term_trend) : undefined,
    // What actually drives the risk score, so a number built from silence is
    // distinguishable from one built from distress.
    riskTopFactors: Array.isArray(row.risk_top_factors)
      ? row.risk_top_factors.map(String).filter(Boolean)
      : undefined,
    riskConfidenceBand: row.risk_calibration_band ? String(row.risk_calibration_band) : undefined,
    sentimentLastUpdatedAt: row.sentiment_last_updated_at
      ? String(row.sentiment_last_updated_at)
      : undefined,
  };
}

function mergeAnalyticsIntoEmployee(base: Employee, aug: AnalyticsAugment): Employee {
  return {
    ...base,
    sentiment: sentimentLabelFromScore(aug.sentiment),
    sentimentScore: aug.sentiment,
    sentimentTrend: aug.trend,
    sentimentDelta: aug.delta,
    riskScore: aug.risk,
    riskLabel: aug.riskLabel,
    riskTopFactors: aug.riskTopFactors?.length ? aug.riskTopFactors : undefined,
    riskConfidenceBand: aug.riskConfidenceBand,
    sentimentLastUpdatedAt: aug.sentimentLastUpdatedAt,
    narrative: aug.narrative,
    spikeAlert: aug.spikeAlert || undefined,
    silentRisk: aug.silentRisk || undefined,
    topTopic: aug.topTopic,
    topEmotion: aug.topEmotion,
    complaints5d: aug.complaints5d || undefined,
    shortTermTrend: aug.shortTermTrend,
    longTermTrend: aug.longTermTrend,
  };
}

/**
 * Pure merge of `/api/v1/users` + `/api/v1/analytics/employees` payloads (also used by the HR directory page for explicit HTTP status handling).
 */
export function mergeEmployeeDirectoryRows(
  users: Array<Record<string, unknown>> | null | undefined,
  analytics: Array<Record<string, unknown>> | null | undefined,
): Employee[] {
  const analyticsRows = analytics ?? [];
  const riskById = new Map<string, AnalyticsAugment>();
  analyticsRows.forEach((row) => {
    const id = String(row.employee_id ?? row.id ?? "");
    if (!id) return;
    riskById.set(id, analyticsAugmentFromRow(row));
  });

  const employeeUsers = users?.filter((u) => String(u.role ?? "").toLowerCase() === "employee");

  if (employeeUsers?.length) {
    return employeeUsers.map((row) => {
      const id = String(row.id ?? "");
      const extra = riskById.get(id);
      const name = String(row.name ?? "Employee");
      const base: Employee = {
        id,
        name,
        role: String(row.designation ?? "Employee"),
        department: String(row.department ?? "Unknown"),
        email: String(row.email ?? ""),
        initials: initialsForName(name),
        joinedAt: "",
        sentiment: "neutral",
        sentimentScore: 50,
        sentimentTrend: "stable",
        sentimentDelta: 0,
        riskScore: 0,
        riskLabel: "Low",
        leaveBalance: 0,
        managerId: row.manager_id ? String(row.manager_id) : undefined,
        location: "—",
      };
      if (!extra) {
        return {
          ...base,
          sentiment: sentimentLabelFromScore(50),
          sentimentScore: 50,
          sentimentTrend: "stable",
          sentimentDelta: 0,
          riskScore: 0,
          riskLabel: "Low",
        };
      }
      return mergeAnalyticsIntoEmployee(base, extra);
    });
  }

  if (!analyticsRows.length) return [];

  return analyticsRows.map((row) => {
    const name = String(row.name ?? "Employee");
    const aug = analyticsAugmentFromRow(row);
    const base: Employee = {
      id: String(row.employee_id ?? row.id ?? ""),
      name,
      role: "Employee",
      department: String(row.department ?? "Unknown"),
      email: "",
      initials: initialsForName(name),
      joinedAt: "",
      sentiment: "neutral",
      sentimentScore: 50,
      sentimentTrend: "stable",
      sentimentDelta: 0,
      riskScore: 0,
      riskLabel: "Low",
      leaveBalance: 0,
      managerId: row.manager_id ? String(row.manager_id) : undefined,
      location: "—",
    };
    return mergeAnalyticsIntoEmployee(base, aug);
  });
}

/** HR directory + analytics fallback for employee insights (risk / sentiment). */
export async function getEmployees(): Promise<Employee[]> {
  const users = await getJson<Array<Record<string, unknown>>>("/api/v1/users");
  const analytics = await getJson<Array<Record<string, unknown>>>("/api/v1/analytics/employees");
  return mergeEmployeeDirectoryRows(users ?? undefined, analytics ?? undefined);
}

export interface UserDetail extends Employee {
  managerId?: string | null;
  managerName?: string | null;
  annualLeaveDays?: number;
  usedLeaveDaysYtd?: number;
  riskConfidence?: number;
  riskCalibrationBand?: string;
  riskFactors?: AttritionRiskFactor[];
  calibratedRiskScore?: number;
}

export interface AttritionRiskFactor {
  name: string;
  description: string;
  direction: string;
  raw_value: number;
  risk_value: number;
  weight: number;
  contribution: number;
  contribution_pct: number;
}

export interface AttritionRiskDetail {
  user_id: string;
  name: string;
  risk_score: number;
  calibrated_risk_score: number;
  risk_level: string;
  confidence: number;
  calibration_band: string;
  factors: AttritionRiskFactor[];
  history: Array<{ date: string; risk_score: number; risk_level: string }>;
}

const sentimentValues: Employee["sentiment"][] = ["positive", "neutral", "watch", "at_risk"];

export async function getUserDetail(userId: string): Promise<UserDetail | null> {
  const [row, attrition, analyticsRows] = await Promise.all([
    getJson<Record<string, unknown>>(`/api/v1/users/${userId}`),
    getJson<AttritionRiskDetail>(`/api/v1/analytics/attrition/${userId}`),
    getJson<Array<Record<string, unknown>>>(`/api/v1/analytics/employees?limit=200`),
  ]);
  if (!row) return null;
  const analyticsRow = (analyticsRows || []).find((item) => String(item.id ?? item.employee_id ?? "") === userId);
  const name = String(row.name ?? "Employee");
  const rawSentiment = String(row.sentiment ?? "neutral");
  const sentiment: Employee["sentiment"] = sentimentValues.includes(rawSentiment as Employee["sentiment"])
    ? (rawSentiment as Employee["sentiment"])
    : "neutral";
  const narrative =
    Array.isArray(analyticsRow?.narrative) ? (analyticsRow.narrative as unknown[]).map(String) : undefined;
  const riskScore = Number(analyticsRow?.risk_score ?? row.risk_score ?? 0);

  return {
    id: String(row.id ?? userId),
    name,
    role: String(row.designation ?? "Employee"),
    department: String(row.department ?? "Unknown"),
    email: String(row.email ?? ""),
    initials: initialsForName(name),
    joinedAt: String(row.joined_at ?? ""),
    sentiment,
    sentimentScore: Number(analyticsRow?.sentiment_score ?? 50),
    sentimentTrend:
      String(analyticsRow?.trend ?? "stable") === "up"
        ? "up"
        : String(analyticsRow?.trend ?? "stable") === "down"
          ? "down"
          : "stable",
    sentimentDelta: Number(analyticsRow?.delta ?? 0),
    riskScore,
    riskLabel:
      String(analyticsRow?.risk_label ?? "Low") === "High"
        ? "High"
        : String(analyticsRow?.risk_label ?? "Low") === "Medium"
          ? "Medium"
          : "Low",
    narrative: narrative?.length ? narrative : undefined,
    spikeAlert: Boolean(analyticsRow?.spike_alert) || undefined,
    silentRisk: Boolean(analyticsRow?.silent_risk) || undefined,
    topTopic: analyticsRow?.top_topic ? String(analyticsRow.top_topic) : undefined,
    topEmotion: analyticsRow?.top_emotion ? String(analyticsRow.top_emotion) : undefined,
    complaints5d: Number(analyticsRow?.complaints_5d ?? 0) || undefined,
    shortTermTrend:
      analyticsRow?.short_term_trend != null ? Number(analyticsRow.short_term_trend) : undefined,
    longTermTrend:
      analyticsRow?.long_term_trend != null ? Number(analyticsRow.long_term_trend) : undefined,
    leaveBalance: Number(row.leave_balance ?? 0),
    managerId: row.manager_id ? String(row.manager_id) : undefined,
    location: String(row.location ?? "—"),
    managerName: row.manager_name ? String(row.manager_name) : null,
    annualLeaveDays: Number(row.annual_leave_days ?? 25),
    usedLeaveDaysYtd: Number(row.used_leave_days_ytd ?? 0),
    riskConfidence: Number(attrition?.confidence ?? 0),
    riskCalibrationBand: String(attrition?.calibration_band ?? ""),
    riskFactors: Array.isArray(attrition?.factors) ? attrition.factors : [],
    calibratedRiskScore: Number(attrition?.calibrated_risk_score ?? row.risk_score ?? 0),
  };
}

export async function getEmployee(id: string): Promise<Employee | undefined> {
  const detail = await getUserDetail(id);
  return detail ?? undefined;
}

export interface TimelineRow {
  date: string;
  text: string;
  tone: string;
}

export async function getEmployeeTimeline(userId: string): Promise<TimelineRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/users/${userId}/timeline`);
  if (!rows) return [];
  return rows.map((row) => ({
    date: String(row.date ?? ""),
    text: String(row.text ?? ""),
    tone: String(row.tone ?? "neutral"),
  }));
}

export async function getManagerTeam(): Promise<Employee[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/analytics/manager/team");
  if (!rows) return [];
  return rows.map((row) => {
    const name = String(row.name ?? "");
    const sentimentScore = Number(row.sentiment_score ?? 0);
    const sentiment: Employee["sentiment"] =
      sentimentScore >= 70 ? "positive" : sentimentScore >= 45 ? "watch" : "at_risk";
    const riskScore = Number(row.risk_score ?? 0);
    return {
      id: String(row.id ?? ""),
      name,
      role: String(row.designation ?? row.role ?? "Employee"),
      department: String(row.department ?? "General"),
      email: String(row.email ?? ""),
      initials: String(row.initials ?? initialsForName(name)),
      joinedAt: "",
      sentiment,
      sentimentScore,
      sentimentTrend: String(row.trend ?? "stable") === "down" ? "down" : String(row.trend ?? "stable") === "up" ? "up" : "stable",
      sentimentDelta: Number(row.delta ?? 0),
      riskScore,
      riskLabel: String(row.risk_label ?? (riskScore >= 70 ? "High" : riskScore >= 40 ? "Medium" : "Low")) as Employee["riskLabel"],
      narrative: Array.isArray(row.narrative) ? row.narrative.map((item) => String(item)) : [],
      spikeAlert: Boolean(row.spike_alert),
      silentRisk: Boolean(row.silent_risk),
      topTopic: row.top_topic ? String(row.top_topic) : undefined,
      topEmotion: row.top_emotion ? String(row.top_emotion) : undefined,
      complaints5d: Number(row.complaints_5d ?? 0),
      shortTermTrend: row.short_term_trend != null ? Number(row.short_term_trend) : undefined,
      longTermTrend: row.long_term_trend != null ? Number(row.long_term_trend) : undefined,
      leaveBalance: Number(row.leave_balance ?? 0),
      location: "—",
    };
  });
}

export interface ManagerSummary {
  team_size: number;
  at_risk_members: number;
  watch_members: number;
  pending_leave_requests: number;
  open_team_tickets: number;
  avg_team_sentiment?: number;
  avg_team_risk?: number;
  high_risk_count?: number;
}

/** Org-wide emotions for HR preview; team-scoped for managers (direct reports only). */
export async function getManagerPageEmotionTrend(
  role: string | undefined,
  days = 14,
): Promise<Array<{ date: string; emotions: Record<string, number> }>> {
  const r = String(role ?? "").toLowerCase();
  const path =
    r === "hr"
      ? `/api/v1/analytics/emotions?days=${days}`
      : `/api/v1/analytics/manager/emotions?days=${days}`;
  const rows = await getJson<Array<Record<string, unknown>>>(path);
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    const rawEmotions = row.emotions && typeof row.emotions === "object" ? (row.emotions as Record<string, unknown>) : {};
    const emotions: Record<string, number> = {};
    Object.entries(rawEmotions).forEach(([emotion, value]) => {
      const numeric = Number(value ?? 0);
      if (!Number.isFinite(numeric)) return;
      emotions[String(emotion)] = Math.max(0, Math.min(100, numeric));
    });
    return { date: String(row.date ?? ""), emotions };
  });
}

/** Classifier path mix: org-wide for HR; team-scoped (direct reports) for managers. */
export async function getManagerPageClassifierTrend(
  role: string | undefined,
  days = 14,
): Promise<Array<{ date: string; sources: Record<string, number> }>> {
  const r = String(role ?? "").toLowerCase();
  const path =
    r === "hr"
      ? `/api/v1/analytics/sentiment/source-drift/timeseries?days=${days}`
      : `/api/v1/analytics/manager/sentiment/source-drift/timeseries?days=${days}`;
  const rows = await getJson<Array<Record<string, unknown>>>(path);
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    const rawSources = row.sources && typeof row.sources === "object" ? (row.sources as Record<string, unknown>) : {};
    const sources: Record<string, number> = {};
    Object.entries(rawSources).forEach(([key, value]) => {
      const numeric = Number(value ?? 0);
      if (!Number.isFinite(numeric)) return;
      sources[String(key)] = Math.max(0, Math.min(100, numeric));
    });
    return { date: String(row.date ?? ""), sources };
  });
}

export async function getManagerSummary(): Promise<ManagerSummary | null> {
  const row = await getJson<Record<string, unknown>>("/api/v1/analytics/manager/dashboard");
  if (!row) return null;
  const employees = Array.isArray(row.employees) ? row.employees : [];
  const atRisk = employees.filter((item) => Number((item as Record<string, unknown>).risk_score ?? 0) >= 70).length;
  const watch = employees.filter((item) => {
    const risk = Number((item as Record<string, unknown>).risk_score ?? 0);
    return risk >= 40 && risk < 70;
  }).length;
  return {
    team_size: Number(row.team_size ?? employees.length),
    at_risk_members: atRisk,
    watch_members: watch,
    pending_leave_requests: 0,
    open_team_tickets: Number(row.open_complaints ?? 0),
    avg_team_sentiment: Number(row.avg_team_sentiment ?? 0),
    avg_team_risk: Number(row.avg_team_risk ?? 0),
    high_risk_count: Number(row.high_risk_count ?? 0),
  };
}

export interface AdminUserRow {
  id: string;
  name: string;
  email: string;
  initials: string;
  department: string;
  role: string;
  active: boolean;
}

export async function getAdminUsers(): Promise<AdminUserRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/users");
  if (!rows) return [];
  return rows.map((row) => {
    const name = String(row.name ?? "");
    const active = String(row.status ?? "active").toLowerCase() === "active";
    return {
      id: String(row.id ?? ""),
      name,
      email: String(row.email ?? ""),
      initials: initialsForName(name),
      department: String(row.department ?? ""),
      role: String(row.role ?? "employee"),
      active,
    };
  });
}
