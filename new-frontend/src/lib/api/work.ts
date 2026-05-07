import type { Survey, Ticket } from "@/lib/domain-types";
import type { UserRole } from "@/contexts/AuthContext";
import { loadLocalTickets, mapBackendTicketToDashboardTicket, mergeTickets, type BackendTicketPayload } from "@/lib/ticket-store";
import { getJson, patchJson, postJson, readStoredSession } from "@/lib/api/client";

interface DashboardInsight {
  id: string;
  title: string;
  detail: string;
  tone: "positive" | "neutral" | "watch" | "at_risk";
  action: string;
  route: string;
}

export interface ManagerPatternInsight {
  manager_id: string;
  manager: string;
  count: number;
}

export interface EmployeeHighlight {
  id: string;
  name: string;
  sentiment_score: number;
  risk_score: number;
  risk_label: string;
  spike_alert: boolean;
  silent_risk: boolean;
  sustained_risk_pattern?: boolean;
  negative_turns_in_window?: number;
  narrative: string[];
  top_topic?: string;
  sentiment_last_updated_at?: string;
  sentiment_confidence?: number;
  sentiment_confidence_band?: "high" | "medium" | "low" | string;
}

/** HR-only: share of sentiment_logs by classifier path (llm / lexicon / hybrid / …). */
export interface SentimentSourceDrift {
  window_days: number;
  total: number;
  by_source: Record<string, number>;
  pct_by_source: Record<string, number>;
}

/** Daily classifier path mix (%), aligned with GET .../sentiment/source-drift/timeseries */
export interface ClassifierSourceTrendPoint {
  date: string;
  sources: Record<string, number>;
}

export interface DashboardData {
  metrics: {
    engagement_score: number;
    total_tickets: number;
    open_tickets: number;
    resolution_rate: number;
  };
  sentiment: Array<{ date: string; positive: number; neutral: number; negative: number }>;
  emotions: Array<{ date: string; emotions: Record<string, number> }>;
  insights: DashboardInsight[];
  aiSummary: string | null;
  managerPattern: ManagerPatternInsight | null;
  employeeHighlights: EmployeeHighlight[];
  sentiment_stale_days: number;
  sustained_risk_window_days: number;
  sustained_risk_min_negative_turns: number;
  sentiment_source_drift: SentimentSourceDrift | null;
  classifier_source_trend: ClassifierSourceTrendPoint[];
  last_chat_sentiment_at: string | null;
}

export interface ActivityItem {
  text: string;
  time: string;
  tag: string;
  tagCls: string;
}

export interface ManagerEffectivenessRow {
  manager_id: string;
  manager_name: string;
  team_size: number;
  avg_sentiment_score: number;
  avg_risk_score: number;
  open_complaints: number;
  engagement_ratio: number;
  effectiveness_score: number;
  effectiveness_label: "strong" | "steady" | "needs_support" | string;
}

export interface AutomationRuleRow {
  id: string;
  name: string;
  event_type: string;
  enabled: boolean;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProactiveSuppressionPolicy {
  enabled: boolean;
  global_daily_max: number;
  break_nudge_cooldown_minutes: number;
  break_nudge_daily_max: number;
  scheduled_reminder_cooldown_minutes: number;
  scheduled_reminder_daily_max: number;
  daily_checkin_followup_cooldown_minutes: number;
  daily_checkin_followup_daily_max: number;
}

export interface IntegrationProviderItem {
  key: string;
  category: string;
  enabled: boolean;
  configured: boolean;
  status: string;
  notes?: string | null;
}

export interface IntegrationSyncResult {
  provider: string;
  category: string;
  status: string;
  dry_run: boolean;
  records_seen: number;
  records_changed: number;
  details: string;
}

export interface HighRiskEmployeeRow {
  user_id: string;
  name: string;
  mood_score: number;
  risk_score: number;
  risk_level: string;
  open_tickets: number;
  last_active: string;
  reasons: string[];
}

export interface WeeklyWellbeingSummary {
  window_days: number;
  high_risk_employees: number;
  followup_signals: number;
  open_tickets: number;
  avg_engagement_score: number;
  top_issues: Array<{ category: string; count: number }>;
}

export async function getTickets(): Promise<Ticket[]> {
  const localTickets = loadLocalTickets();
  const backend = await getJson<BackendTicketPayload[]>("/api/v1/tickets");
  if (!backend) return mergeTickets(localTickets);
  const backendTickets = backend.map(mapBackendTicketToDashboardTicket);
  return mergeTickets(backendTickets, localTickets);
}

export async function getTicket(id: string): Promise<Ticket | undefined> {
  const tickets = await getTickets();
  return tickets.find((ticket) => ticket.id === id);
}

export async function getSurveys(): Promise<Survey[]> {
  const session = readStoredSession();
  const role = session?.role as UserRole | undefined;
  const path = role === "hr" ? "/api/v1/surveys/hr-summary" : "/api/v1/surveys";
  const rows = await getJson<Array<Record<string, unknown>>>(path);
  if (!rows) return [];

  return rows.map((row) => {
    const invited = Number(row.invited ?? 0);
    const responses = Number(row.responses ?? 0);
    const sentimentRaw = String(row.sentiment ?? "neutral").toLowerCase();
    const sentiment: Survey["sentiment"] =
      sentimentRaw === "positive" || sentimentRaw === "watch" || sentimentRaw === "at_risk" ? sentimentRaw : "neutral";
    const statusRaw = String(row.status ?? (row.is_active ? "live" : "closed")).toLowerCase();
    const status: Survey["status"] =
      statusRaw === "draft" || statusRaw === "closed" || statusRaw === "live" ? statusRaw : "live";
    return {
      id: String(row.id ?? ""),
      title: String(row.title ?? "Untitled survey"),
      audience: String(row.audience ?? "All employees"),
      responses,
      invited: invited || 1,
      sentiment,
      status,
      closedAt: row.closed_at ? String(row.closed_at) : undefined,
    };
  });
}

export async function createSurvey(input: {
  title: string;
  description?: string;
  allow_anonymous?: boolean;
  questions?: Array<Record<string, unknown>>;
}): Promise<boolean> {
  const row = await postJson<Record<string, unknown>>("/api/v1/surveys", {
    title: input.title,
    description: input.description ?? "Pulse survey created from MARK Admin UI.",
    allow_anonymous: Boolean(input.allow_anonymous),
    questions:
      input.questions ??
      [
        { id: "q1", type: "rating", question: "How are you feeling this week (0-10)?", required: true },
        { id: "q2", type: "text", question: "What would improve your week?", required: false },
      ],
  });
  return Boolean(row);
}

function parseManagerPattern(raw: unknown): ManagerPatternInsight | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const count = Number(o.count ?? 0);
  if (count < 1) return null;
  return {
    manager_id: String(o.manager_id ?? ""),
    manager: String(o.manager ?? "Unknown"),
    count,
  };
}

function parseEmployeeHighlights(employeesRaw: unknown): EmployeeHighlight[] {
  if (!Array.isArray(employeesRaw)) return [];
  const rows = employeesRaw as Record<string, unknown>[];
  const scored = rows
    .map((row) => {
      const id = String(row.id ?? row.employee_id ?? "");
      const risk = Number(row.risk_score ?? 0);
      const spike = Boolean(row.spike_alert);
      const silent = Boolean(row.silent_risk);
      const sustained = Boolean(row.sustained_risk_pattern);
      const negTurns =
        row.negative_turns_in_window != null ? Number(row.negative_turns_in_window) : undefined;
      const narrative = Array.isArray(row.narrative) ? row.narrative.map(String) : [];
      const priority =
        (silent ? 4 : 0) +
        (sustained ? 5 : 0) +
        (spike ? 3 : 0) +
        (risk >= 70 ? 2 : risk >= 40 ? 1 : 0);
      return {
        id,
        name: String(row.name ?? "Employee"),
        sentiment_score: Number(row.sentiment_score ?? 0),
        risk_score: risk,
        risk_label: String(row.risk_label ?? "Low"),
        spike_alert: spike,
        silent_risk: silent,
        sustained_risk_pattern: sustained || undefined,
        negative_turns_in_window: Number.isFinite(negTurns) ? negTurns : undefined,
        narrative,
        top_topic: row.top_topic ? String(row.top_topic) : undefined,
        sentiment_last_updated_at:
          row.sentiment_last_updated_at != null ? String(row.sentiment_last_updated_at) : undefined,
        sentiment_confidence:
          row.sentiment_confidence != null ? Number(row.sentiment_confidence) : undefined,
        sentiment_confidence_band:
          row.sentiment_confidence_band != null ? String(row.sentiment_confidence_band) : undefined,
        priority,
      };
    })
    .filter((e) => e.id && (e.priority > 0 || e.narrative.length > 0))
    .sort((a, b) => b.priority - a.priority)
    .slice(0, 8)
    .map(({ priority: _p, ...rest }) => rest);
  return scored;
}

function parseSentimentSourceDrift(raw: unknown): SentimentSourceDrift | null {
  if (!raw || typeof raw !== "object") return null;
  const driftRaw = raw as Record<string, unknown>;
  const total = Number(driftRaw.total ?? 0);
  const wd = Number(driftRaw.window_days ?? 7);
  if (!Number.isFinite(total) || total < 0 || !Number.isFinite(wd)) return null;
  const byRaw =
    driftRaw.by_source && typeof driftRaw.by_source === "object" ? driftRaw.by_source : {};
  const pctRaw =
    driftRaw.pct_by_source && typeof driftRaw.pct_by_source === "object" ? driftRaw.pct_by_source : {};
  const by_source: Record<string, number> = {};
  const pct_by_source: Record<string, number> = {};
  Object.entries(byRaw as Record<string, unknown>).forEach(([k, v]) => {
    const n = Number(v ?? 0);
    if (Number.isFinite(n)) by_source[k] = n;
  });
  Object.entries(pctRaw as Record<string, unknown>).forEach(([k, v]) => {
    const n = Number(v ?? 0);
    if (Number.isFinite(n)) pct_by_source[k] = n;
  });
  return { window_days: wd, total, by_source, pct_by_source };
}

export async function getDashboardData(): Promise<DashboardData | null> {
  const dashboard = await getJson<Record<string, unknown>>("/api/v1/analytics/dashboard?drift_days=7");
  if (!dashboard) return null;

  const metricsRaw = dashboard.metrics as Record<string, unknown> | undefined;
  const sentiment = Array.isArray(dashboard.sentiment) ? dashboard.sentiment : [];
  const [emotionRows, insightsRows, sourceTrendRaw] = await Promise.all([
    getJson<Array<Record<string, unknown>>>("/api/v1/analytics/emotions?days=14"),
    getJson<Array<Record<string, unknown>>>("/api/v1/analytics/insights"),
    getJson<Array<Record<string, unknown>>>("/api/v1/analytics/sentiment/source-drift/timeseries?days=14").catch(
      () => [],
    ),
  ]);

  let sentiment_source_drift = parseSentimentSourceDrift(dashboard.sentiment_source_drift);
  if (!sentiment_source_drift) {
    const driftFallback = await getJson<Record<string, unknown>>(
      "/api/v1/analytics/sentiment/source-drift?days=7",
    ).catch(() => null);
    sentiment_source_drift = parseSentimentSourceDrift(driftFallback);
  }

  const classifier_source_trend: ClassifierSourceTrendPoint[] = Array.isArray(sourceTrendRaw)
    ? sourceTrendRaw.map((row) => {
        const rawSources =
          row.sources && typeof row.sources === "object" ? (row.sources as Record<string, unknown>) : {};
        const sources: Record<string, number> = {};
        Object.entries(rawSources).forEach(([k, v]) => {
          const n = Number(v ?? 0);
          if (Number.isFinite(n)) sources[k] = Math.max(0, Math.min(100, n));
        });
        return { date: String(row.date ?? ""), sources };
      })
    : [];

  const insights: DashboardInsight[] = (insightsRows || []).slice(0, 6).map((row) => ({
    id: String(row.id ?? crypto.randomUUID()),
    title: String(row.title ?? "Insight"),
    detail: String(row.description ?? "No details available."),
    tone:
      String(row.severity ?? "") === "critical"
        ? "at_risk"
        : String(row.severity ?? "") === "warning"
          ? "watch"
          : "neutral",
    action: "Review",
    route: "/employees",
  }));

  const managerPattern = parseManagerPattern(dashboard.manager_pattern);
  const employeeHighlights = parseEmployeeHighlights(dashboard.employees);

  return {
    metrics: {
      engagement_score: Number(metricsRaw?.engagement_score ?? 0),
      total_tickets: Number(metricsRaw?.total_tickets ?? 0),
      open_tickets: Number(metricsRaw?.open_tickets ?? 0),
      resolution_rate: Number(metricsRaw?.resolution_rate ?? 0),
    },
    sentiment: sentiment.map((point) => {
      const row = point as Record<string, unknown>;
      return {
        date: String(row.date ?? ""),
        positive: Number(row.positive ?? 0),
        neutral: Number(row.neutral ?? 0),
        negative: Number(row.negative ?? 0),
      };
    }),
    emotions: Array.isArray(emotionRows)
      ? emotionRows.map((row) => {
          const rawEmotions = row.emotions && typeof row.emotions === "object" ? (row.emotions as Record<string, unknown>) : {};
          const normalized: Record<string, number> = {};
          Object.entries(rawEmotions).forEach(([emotion, value]) => {
            const numeric = Number(value ?? 0);
            if (!Number.isFinite(numeric)) return;
            normalized[String(emotion)] = Math.max(0, Math.min(100, numeric));
          });
          return {
            date: String(row.date ?? ""),
            emotions: normalized,
          };
        })
      : [],
    insights,
    aiSummary: typeof dashboard.ai_summary === "string" ? dashboard.ai_summary : null,
    managerPattern,
    employeeHighlights,
    sentiment_stale_days: Number(dashboard.sentiment_stale_days ?? 7),
    sustained_risk_window_days: Number(dashboard.sustained_risk_window_days ?? 7),
    sustained_risk_min_negative_turns: Number(dashboard.sustained_risk_min_negative_turns ?? 3),
    sentiment_source_drift,
    classifier_source_trend,
    last_chat_sentiment_at: typeof dashboard.last_chat_sentiment_at === "string" ? dashboard.last_chat_sentiment_at : null,
  };
}

export async function getRecentActivity(): Promise<ActivityItem[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/portal/hr/recent-activity");
  if (!rows) return [];
  return rows.map((row) => ({
    text: String(row.text ?? ""),
    time: String(row.time ?? ""),
    tag: String(row.tag ?? ""),
    tagCls: String(row.tag_cls ?? row.tagCls ?? "bg-secondary text-foreground"),
  }));
}

export async function getManagerEffectiveness(limit = 25): Promise<ManagerEffectivenessRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/analytics/manager-effectiveness?limit=${limit}`);
  if (!rows) return [];
  return rows.map((row) => ({
    manager_id: String(row.manager_id ?? ""),
    manager_name: String(row.manager_name ?? "Manager"),
    team_size: Number(row.team_size ?? 0),
    avg_sentiment_score: Number(row.avg_sentiment_score ?? 0),
    avg_risk_score: Number(row.avg_risk_score ?? 0),
    open_complaints: Number(row.open_complaints ?? 0),
    engagement_ratio: Number(row.engagement_ratio ?? 0),
    effectiveness_score: Number(row.effectiveness_score ?? 0),
    effectiveness_label: String(row.effectiveness_label ?? "steady"),
  }));
}

export async function listAutomationRules(): Promise<AutomationRuleRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/automations/rules");
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    name: String(row.name ?? ""),
    event_type: String(row.event_type ?? "ticket_created"),
    enabled: Boolean(row.enabled),
    conditions: (row.conditions as Record<string, unknown>) || {},
    actions: (row.actions as Record<string, unknown>) || {},
    created_by: row.created_by ? String(row.created_by) : null,
    created_at: String(row.created_at ?? ""),
    updated_at: String(row.updated_at ?? ""),
  }));
}

export async function createAutomationRule(input: {
  name: string;
  eventType?: string;
  conditions?: Record<string, unknown>;
  actions?: Record<string, unknown>;
}): Promise<AutomationRuleRow | null> {
  const row = await postJson<Record<string, unknown>>("/api/v1/automations/rules", {
    name: input.name,
    event_type: input.eventType ?? "ticket_created",
    conditions: input.conditions ?? {},
    actions: input.actions ?? {},
  });
  if (!row) return null;
  return {
    id: String(row.id ?? ""),
    name: String(row.name ?? ""),
    event_type: String(row.event_type ?? "ticket_created"),
    enabled: Boolean(row.enabled),
    conditions: (row.conditions as Record<string, unknown>) || {},
    actions: (row.actions as Record<string, unknown>) || {},
    created_by: row.created_by ? String(row.created_by) : null,
    created_at: String(row.created_at ?? ""),
    updated_at: String(row.updated_at ?? ""),
  };
}

export async function updateAutomationRule(ruleId: string, input: {
  name?: string;
  enabled?: boolean;
  conditions?: Record<string, unknown>;
  actions?: Record<string, unknown>;
}): Promise<AutomationRuleRow | null> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/automations/rules/${ruleId}`, input);
  if (!row) return null;
  return {
    id: String(row.id ?? ""),
    name: String(row.name ?? ""),
    event_type: String(row.event_type ?? "ticket_created"),
    enabled: Boolean(row.enabled),
    conditions: (row.conditions as Record<string, unknown>) || {},
    actions: (row.actions as Record<string, unknown>) || {},
    created_by: row.created_by ? String(row.created_by) : null,
    created_at: String(row.created_at ?? ""),
    updated_at: String(row.updated_at ?? ""),
  };
}

export async function getProactiveSuppressionPolicy(): Promise<ProactiveSuppressionPolicy | null> {
  const row = await getJson<Record<string, unknown>>("/api/v1/wellbeing/policy-suppression");
  if (!row) return null;
  return {
    enabled: Boolean(row.enabled),
    global_daily_max: Number(row.global_daily_max ?? 8),
    break_nudge_cooldown_minutes: Number(row.break_nudge_cooldown_minutes ?? 60),
    break_nudge_daily_max: Number(row.break_nudge_daily_max ?? 2),
    scheduled_reminder_cooldown_minutes: Number(row.scheduled_reminder_cooldown_minutes ?? 20),
    scheduled_reminder_daily_max: Number(row.scheduled_reminder_daily_max ?? 10),
    daily_checkin_followup_cooldown_minutes: Number(row.daily_checkin_followup_cooldown_minutes ?? 240),
    daily_checkin_followup_daily_max: Number(row.daily_checkin_followup_daily_max ?? 1),
  };
}

export async function updateProactiveSuppressionPolicy(
  input: Partial<ProactiveSuppressionPolicy>,
): Promise<ProactiveSuppressionPolicy | null> {
  const row = await patchJson<Record<string, unknown>>("/api/v1/wellbeing/policy-suppression", input);
  if (!row) return null;
  return {
    enabled: Boolean(row.enabled),
    global_daily_max: Number(row.global_daily_max ?? 8),
    break_nudge_cooldown_minutes: Number(row.break_nudge_cooldown_minutes ?? 60),
    break_nudge_daily_max: Number(row.break_nudge_daily_max ?? 2),
    scheduled_reminder_cooldown_minutes: Number(row.scheduled_reminder_cooldown_minutes ?? 20),
    scheduled_reminder_daily_max: Number(row.scheduled_reminder_daily_max ?? 10),
    daily_checkin_followup_cooldown_minutes: Number(row.daily_checkin_followup_cooldown_minutes ?? 240),
    daily_checkin_followup_daily_max: Number(row.daily_checkin_followup_daily_max ?? 1),
  };
}

export async function listIntegrationProviders(): Promise<IntegrationProviderItem[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/integrations/providers");
  if (!rows) return [];
  return rows.map((row) => ({
    key: String(row.key ?? ""),
    category: String(row.category ?? "other"),
    enabled: Boolean(row.enabled),
    configured: Boolean(row.configured),
    status: String(row.status ?? "unknown"),
    notes: row.notes ? String(row.notes) : null,
  }));
}

export async function triggerHrmsSync(provider: string, dryRun = true): Promise<IntegrationSyncResult | null> {
  const row = await postJson<Record<string, unknown>>("/api/v1/integrations/hrms/sync", {
    provider,
    dry_run: dryRun,
    scope: "full",
  });
  if (!row) return null;
  return {
    provider: String(row.provider ?? provider),
    category: String(row.category ?? "hrms"),
    status: String(row.status ?? "ok"),
    dry_run: Boolean(row.dry_run),
    records_seen: Number(row.records_seen ?? 0),
    records_changed: Number(row.records_changed ?? 0),
    details: String(row.details ?? ""),
  };
}

export async function triggerPayrollSync(provider: string, dryRun = true): Promise<IntegrationSyncResult | null> {
  const row = await postJson<Record<string, unknown>>("/api/v1/integrations/payroll/sync", {
    provider,
    dry_run: dryRun,
    scope: "full",
  });
  if (!row) return null;
  return {
    provider: String(row.provider ?? provider),
    category: String(row.category ?? "payroll"),
    status: String(row.status ?? "ok"),
    dry_run: Boolean(row.dry_run),
    records_seen: Number(row.records_seen ?? 0),
    records_changed: Number(row.records_changed ?? 0),
    details: String(row.details ?? ""),
  };
}

export async function getWellbeingHighRisk(limit = 10): Promise<HighRiskEmployeeRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/wellbeing/high-risk?limit=${limit}`);
  if (!rows) return [];
  return rows.map((row) => ({
    user_id: String(row.user_id ?? ""),
    name: String(row.name ?? "Employee"),
    mood_score: Number(row.mood_score ?? 0),
    risk_score: Number(row.risk_score ?? 0),
    risk_level: String(row.risk_level ?? "low"),
    open_tickets: Number(row.open_tickets ?? 0),
    last_active: String(row.last_active ?? "Unknown"),
    reasons: Array.isArray(row.reasons) ? row.reasons.map((item) => String(item)) : [],
  }));
}

export async function getWeeklyWellbeingSummary(): Promise<WeeklyWellbeingSummary | null> {
  const row = await getJson<Record<string, unknown>>("/api/v1/wellbeing/weekly-summary");
  if (!row) return null;
  return {
    window_days: Number(row.window_days ?? 7),
    high_risk_employees: Number(row.high_risk_employees ?? 0),
    followup_signals: Number(row.followup_signals ?? 0),
    open_tickets: Number(row.open_tickets ?? 0),
    avg_engagement_score: Number(row.avg_engagement_score ?? 0),
    top_issues: Array.isArray(row.top_issues)
      ? row.top_issues.map((item) => {
          const record = item as Record<string, unknown>;
          return {
            category: String(record.category ?? "general"),
            count: Number(record.count ?? 0),
          };
        })
      : [],
  };
}

export interface TicketAssignee {
  id: string;
  name: string;
  email: string;
  role: string;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_id?: string | null;
  message_text: string;
  is_internal?: boolean;
  created_at: string;
}

export interface TicketActionLog {
  id: string;
  ticket_id: string;
  actor_id?: string | null;
  action_type: string;
  details?: string | null;
  created_at: string;
}

export interface HrNotificationRow {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  severity: string;
  is_read: boolean;
  created_at: string;
}

export async function listTicketAssignees(): Promise<TicketAssignee[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/tickets/assignees");
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    name: String(row.name ?? "HR User"),
    email: String(row.email ?? ""),
    role: String(row.role ?? "hr"),
  }));
}

export async function assignTicket(ticketId: string, assigneeId: string): Promise<Ticket | null> {
  const row = await postJson<BackendTicketPayload>(`/api/v1/tickets/${ticketId}/assign`, { assignee_id: assigneeId });
  return row ? mapBackendTicketToDashboardTicket(row) : null;
}

export async function escalateTicket(ticketId: string, reason: string): Promise<Ticket | null> {
  const row = await postJson<BackendTicketPayload>(`/api/v1/tickets/${ticketId}/escalate`, { reason });
  return row ? mapBackendTicketToDashboardTicket(row) : null;
}

export async function scheduleTicketCheckin(ticketId: string, notes?: string): Promise<boolean> {
  const payload: Record<string, unknown> = {};
  if (notes?.trim()) payload.notes = notes.trim();
  const row = await postJson<Record<string, unknown>>(`/api/v1/tickets/${ticketId}/schedule-checkin`, payload);
  return Boolean(row);
}

export async function getTicketMessages(ticketId: string): Promise<TicketMessage[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/tickets/${ticketId}/messages`);
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    ticket_id: String(row.ticket_id ?? ticketId),
    sender_id: row.sender_id ? String(row.sender_id) : null,
    message_text: String(row.message_text ?? ""),
    is_internal: Boolean(row.is_internal),
    created_at: String(row.created_at ?? ""),
  }));
}

export async function getTicketActionLogs(ticketId: string): Promise<TicketActionLog[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/tickets/${ticketId}/actions`);
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    ticket_id: String(row.ticket_id ?? ticketId),
    actor_id: row.actor_id ? String(row.actor_id) : null,
    action_type: String(row.action_type ?? ""),
    details: row.details ? String(row.details) : null,
    created_at: String(row.created_at ?? ""),
  }));
}

export async function getRelatedTickets(ticketId: string): Promise<Ticket[]> {
  const rows = await getJson<BackendTicketPayload[]>(`/api/v1/tickets/${ticketId}/related`);
  if (!rows) return [];
  return rows.map(mapBackendTicketToDashboardTicket);
}

export async function getHrNotifications(limit = 20): Promise<HrNotificationRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/portal/hr/notifications?limit=${limit}`);
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    title: String(row.title ?? "Notification"),
    body: String(row.body ?? ""),
    notification_type: String(row.notification_type ?? "ticket_update"),
    severity: String(row.severity ?? "info"),
    is_read: Boolean(row.is_read),
    created_at: String(row.created_at ?? ""),
  }));
}

export async function markHrNotificationRead(notificationId: string): Promise<boolean> {
  const row = await postJson<Record<string, unknown>>(`/api/v1/portal/hr/notifications/${notificationId}/read`, {});
  return Boolean(row && row.ok !== false);
}

export async function addTicketMessage(ticketId: string, messageText: string): Promise<boolean> {
  const row = await postJson<Record<string, unknown>>(`/api/v1/tickets/${ticketId}/messages`, { message_text: messageText });
  return Boolean(row);
}

export async function addInternalTicketNote(ticketId: string, noteText: string): Promise<boolean> {
  const row = await postJson<Record<string, unknown>>(`/api/v1/tickets/${ticketId}/internal-notes`, { message_text: noteText });
  return Boolean(row);
}

export async function markTicketInProgress(ticketId: string): Promise<Ticket | null> {
  const row = await patchJson<BackendTicketPayload>(`/api/v1/tickets/${ticketId}`, { status: "in_progress" });
  return row ? mapBackendTicketToDashboardTicket(row) : null;
}

export async function closeTicket(ticketId: string, resolutionNote?: string): Promise<Ticket | null> {
  const payload: Record<string, unknown> = {};
  if (resolutionNote?.trim()) payload.resolution_note = resolutionNote.trim();
  const row = await postJson<BackendTicketPayload>(`/api/v1/tickets/${ticketId}/close`, payload);
  return row ? mapBackendTicketToDashboardTicket(row) : null;
}
