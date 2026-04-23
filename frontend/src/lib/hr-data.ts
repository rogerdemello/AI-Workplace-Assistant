import { supabase } from '@/lib/supabase';
import { ensureBackendAuthToken } from '@/lib/backend-auth';

export type TicketStatus = 'Open' | 'In Review' | 'Resolved' | 'Escalated' | 'Closed';

export interface SentimentPoint {
  date: string;
  positive: number;
  neutral: number;
  negative: number;
}

export interface TicketRow {
  id: string;
  employeeId: string;
  issue: string;
  against: string;
  status: TicketStatus;
  anonymous: boolean;
  createdAt: string;
  category: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  assignedTo?: string | null;
  slaDueAt?: string | null;
  slaWarning?: boolean;
}

export interface EmployeeInsightRow {
  id: string;
  employeeId: string;
  name: string;
  sentimentScore: number;
  riskScore: number;
  lastActive: string;
  department: string;
}

export interface DashboardMetrics {
  engagementScore: number;
  riskLevel: 'Low' | 'Medium' | 'High';
  openTickets: number;
  totalTickets: number;
  aiSummary: string;
  departmentsInView: number;
  enps?: number;
  attritionRiskPct?: number;
  activeUsers?: number;
}

export interface DashboardData {
  metrics: DashboardMetrics;
  sentimentPoints: SentimentPoint[];
  tickets: TicketRow[];
  employees: EmployeeInsightRow[];
  weeklyQuality: WeeklyQuality;
  departmentBreakdown?: Array<{
    department: string;
    positive: number;
    neutral: number;
    negative: number;
    score: number;
    total_messages: number;
  }>;
}

export interface WeeklyQuality {
  windowDays: number;
  feedbackResponses: number;
  avgCsat: number;
  helpfulRate: number;
  detractorRate: number;
  avgFirstResponseSeconds: number;
  conversationsMeasured: number;
  qualityLabel: string;
}

function emptyDashboard(aiSummary: string): DashboardData {
  return {
    metrics: {
      engagementScore: 0,
      riskLevel: 'Low',
      openTickets: 0,
      totalTickets: 0,
      aiSummary,
      departmentsInView: 0,
    },
    sentimentPoints: [],
    tickets: [],
    employees: [],
    weeklyQuality: defaultWeeklyQuality(),
  };
}

function defaultWeeklyQuality(): WeeklyQuality {
  return {
    windowDays: 7,
    feedbackResponses: 0,
    avgCsat: 0,
    helpfulRate: 0,
    detractorRate: 0,
    avgFirstResponseSeconds: 0,
    conversationsMeasured: 0,
    qualityLabel: 'Insufficient feedback',
  };
}



function average(values: number[]): number {
  if (!values.length) {
    return 0;
  }

  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function riskLabel(score: number): 'Low' | 'Medium' | 'High' {
  if (score >= 70) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
}

function isOpenTicketStatus(status: TicketStatus): boolean {
  return status !== 'Resolved' && status !== 'Closed';
}

export function ticketStatusLabel(status: string): TicketStatus {
  const value = status.toLowerCase();
  if (value === 'resolved') return 'Resolved';
  if (value === 'closed') return 'Closed';
  if (value === 'escalated') return 'Escalated';
  if (value === 'in_progress') return 'In Review';
  return 'Open';
}

/** Map FastAPI `TicketResponse` fields to dashboard table rows. */
export function mapFastApiTicketToRow(t: {
  id: string;
  user_id: string;
  query: string;
  category: string;
  status: string;
  created_at: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  assigned_to?: string | null;
  sla_due_at?: string | null;
  sla_warning?: boolean;
}): TicketRow {
  return {
    id: String(t.id),
    employeeId: String(t.user_id).replace(/-/g, '').slice(0, 8).toUpperCase(),
    issue: t.query,
    against: t.category,
    status: ticketStatusLabel(String(t.status ?? 'open')),
    anonymous: false,
    createdAt: String(t.created_at ?? new Date().toISOString()),
    category: String(t.category ?? 'General'),
    priority: (t.priority ?? 'medium') as TicketRow['priority'],
    assignedTo: t.assigned_to ?? null,
    slaDueAt: t.sla_due_at ?? null,
    slaWarning: Boolean(t.sla_warning),
  };
}

const API_BASE = () =>
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')) ||
  'http://127.0.0.1:8000';

/**
 * Shape returned by GET /hr/dashboard (the upgraded hr_dashboard route).
 */
interface HrDashboardPayload {
  engagement_score: number;
  enps: number;
  risk_level: 'Low' | 'Medium' | 'High';
  attrition_risk_pct: number;
  open_tickets: number;
  total_tickets: number;
  active_users: number;
  resolution_rate: number;
  avg_response_time: number;
  /** Daily sentiment trend for the last N days */
  sentiment_trend: SentimentPoint[];
  department_breakdown: Array<{
    department: string;
    positive: number;
    neutral: number;
    negative: number;
    score: number;
    total_messages: number;
  }>;
  employees: Array<{
    id: string;
    employee_id: string;
    name: string;
    sentiment_score: number;
    risk_score: number;
    last_active: string;
    department: string;
  }>;
  ai_summary: string;
  weekly_quality?: {
    window_days: number;
    feedback_responses: number;
    avg_csat: number;
    helpful_rate: number;
    detractor_rate: number;
    avg_first_response_seconds: number;
    conversations_measured: number;
    quality_label: string;
  };
}

/**
 * Fetch the full HR dashboard bundle from GET /hr/dashboard.
 * This is the rich SQLAlchemy-powered endpoint with eNPS, dept breakdown, etc.
 */
async function fetchHrDashboardBundle(): Promise<HrDashboardPayload | null> {
  if (typeof window === 'undefined') return null;
  await ensureBackendAuthToken();
  const token = localStorage.getItem('auth_token');
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE()}/hr/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!res.ok) {
      console.warn('[hr-data] /hr/dashboard returned', res.status, res.statusText);
      return null;
    }
    return (await res.json()) as HrDashboardPayload;
  } catch {
    return null;
  }
}

function mapBundleEmployees(rows: HrDashboardPayload['employees']): EmployeeInsightRow[] {
  return rows.map((e) => ({
    id: e.id,
    employeeId: e.employee_id,
    name: e.name,
    sentimentScore: e.sentiment_score,
    riskScore: e.risk_score,
    lastActive: e.last_active,
    department: e.department,
  }));
}

function distinctDepartments(employees: EmployeeInsightRow[]): number {
  return new Set(employees.map((e) => e.department)).size;
}

function mapWeeklyQuality(row: HrDashboardPayload['weekly_quality'] | undefined): WeeklyQuality {
  if (!row) {
    return defaultWeeklyQuality();
  }

  return {
    windowDays: Number(row.window_days ?? 7),
    feedbackResponses: Number(row.feedback_responses ?? 0),
    avgCsat: Number(row.avg_csat ?? 0),
    helpfulRate: Number(row.helpful_rate ?? 0),
    detractorRate: Number(row.detractor_rate ?? 0),
    avgFirstResponseSeconds: Number(row.avg_first_response_seconds ?? 0),
    conversationsMeasured: Number(row.conversations_measured ?? 0),
    qualityLabel: String(row.quality_label ?? 'Insufficient feedback'),
  };
}

/**
 * Tickets created in chat go to FastAPI Postgres (`POST /api/v1/tickets`), not Supabase.
 * HR dashboard must load from the same API when the user has `auth_token`.
 */
async function fetchTicketsFromFastAPI(): Promise<TicketRow[] | null> {
  if (typeof window === 'undefined') {
    return null;
  }
  await ensureBackendAuthToken();
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return null;
  }
  try {
    const res = await fetch(`${API_BASE().replace(/\/$/, '')}/api/v1/tickets`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    if (!res.ok) {
      return null;
    }
    const rows = (await res.json()) as Array<{
      id: string;
      user_id: string;
      query: string;
      category: string;
      status: string;
      created_at: string;
      priority?: 'low' | 'medium' | 'high' | 'critical';
      assigned_to?: string | null;
      sla_due_at?: string | null;
      sla_warning?: boolean;
    }>;
    return rows.map((ticket) => mapFastApiTicketToRow(ticket));
  } catch {
    return null;
  }
}

export async function loadDashboardData(): Promise<DashboardData> {
  await ensureBackendAuthToken();
  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('auth_token');

  const [apiTickets, bundle] = await Promise.all([
    fetchTicketsFromFastAPI(),
    fetchHrDashboardBundle(),
  ]);

  if (hasToken) {
    const mappedTickets: TicketRow[] = apiTickets !== null ? apiTickets : [];
    const openTicketsCount = mappedTickets.filter((ticket) => isOpenTicketStatus(ticket.status)).length;

    if (bundle) {
      const mappedEmployees = mapBundleEmployees(bundle.employees);
      const avgRisk = mappedEmployees.length ? average(mappedEmployees.map((e) => e.riskScore)) : 0;
      const sentimentPoints = (bundle.sentiment_trend ?? []).length > 0 ? bundle.sentiment_trend : [];

      return {
        metrics: {
          engagementScore: Math.round(bundle.engagement_score),
          riskLevel: bundle.risk_level ?? riskLabel(avgRisk),
          openTickets: openTicketsCount,
          totalTickets: mappedTickets.length,
          aiSummary: bundle.ai_summary,
          departmentsInView: Math.max(0, distinctDepartments(mappedEmployees)),
          enps: bundle.enps,
          attritionRiskPct: bundle.attrition_risk_pct,
          activeUsers: bundle.active_users,
        },
        sentimentPoints,
        tickets: mappedTickets,
        employees: mappedEmployees,
        weeklyQuality: mapWeeklyQuality(bundle.weekly_quality),
        departmentBreakdown: bundle.department_breakdown,
      };
    }

    return {
      metrics: {
        engagementScore: 0,
        riskLevel: 'Low',
        openTickets: openTicketsCount,
        totalTickets: mappedTickets.length,
        aiSummary:
          'Could not load /hr/dashboard. Verify FastAPI is running, you are signed in as HR (or admin), and NEXT_PUBLIC_API_URL points to the API. Tickets below still load from /api/v1/tickets when available.',
        departmentsInView: 0,
      },
      sentimentPoints: [],
      tickets: mappedTickets,
      employees: [],
      weeklyQuality: defaultWeeklyQuality(),
    };
  }

  return emptyDashboard('Sign in as HR to load the dashboard.');
}

export async function persistChatMessage(input: {
  conversationId?: string;
  role: 'user' | 'assistant';
  content: string;
  sentiment?: 'positive' | 'neutral' | 'negative';
}): Promise<void> {
  if (!supabase) {
    return;
  }

  await supabase.from('messages').insert({
    conversation_id: input.conversationId ?? null,
    sender: input.role === 'assistant' ? 'bot' : 'user',
    message_text: input.content,
    sentiment: input.sentiment ?? 'neutral',
  });
}