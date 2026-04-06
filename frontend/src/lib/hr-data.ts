import { supabase } from '@/lib/supabase';
import { ensureBackendAuthToken } from '@/lib/backend-auth';

export type TicketStatus = 'Open' | 'In Review' | 'Resolved' | 'Escalated';

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
}

export interface DashboardData {
  metrics: DashboardMetrics;
  sentimentPoints: SentimentPoint[];
  tickets: TicketRow[];
  employees: EmployeeInsightRow[];
}

interface BackendUserRow {
  id: string;
  employee_id: string | null;
  name: string;
  department_id: string | null;
  updated_at: string | null;
}

interface BackendDepartmentRow {
  id: string;
  name: string;
}

interface BackendRiskRow {
  user_id: string;
  risk_score: number;
}

interface BackendSentimentRow {
  user_id: string;
  score: number;
  created_at: string;
}

const fallbackSentiment: SentimentPoint[] = [
  { date: '2026-03-30', positive: 54, neutral: 28, negative: 18 },
  { date: '2026-03-31', positive: 58, neutral: 26, negative: 16 },
  { date: '2026-04-01', positive: 61, neutral: 24, negative: 15 },
  { date: '2026-04-02', positive: 63, neutral: 23, negative: 14 },
  { date: '2026-04-03', positive: 60, neutral: 25, negative: 15 },
  { date: '2026-04-04', positive: 66, neutral: 22, negative: 12 },
  { date: '2026-04-05', positive: 69, neutral: 20, negative: 11 },
];

const fallbackTickets: TicketRow[] = [
  { id: 'T-1001', employeeId: 'EMP-204', issue: 'Payroll tax deduction looks incorrect', against: 'Payroll', status: 'Open', anonymous: false, createdAt: '2026-04-05T08:15:00Z', category: 'Payroll' },
  { id: 'T-1002', employeeId: 'EMP-118', issue: 'Need two days leave for family event', against: 'People Ops', status: 'In Review', anonymous: false, createdAt: '2026-04-04T12:05:00Z', category: 'Leave' },
  { id: 'T-1003', employeeId: 'EMP-331', issue: 'Manager communication has been escalating stress', against: 'Engineering', status: 'Escalated', anonymous: true, createdAt: '2026-04-03T18:20:00Z', category: 'Complaint' },
  { id: 'T-1004', employeeId: 'EMP-087', issue: 'Question about remote work policy', against: 'People Ops', status: 'Resolved', anonymous: false, createdAt: '2026-04-02T09:40:00Z', category: 'Policy' },
];

const fallbackEmployees: EmployeeInsightRow[] = [
  { id: '1', employeeId: 'EMP-204', name: 'Sarah Connor', sentimentScore: 84, riskScore: 22, lastActive: '10 mins ago', department: 'Engineering' },
  { id: '2', employeeId: 'EMP-118', name: 'John Smith', sentimentScore: 46, riskScore: 74, lastActive: '2 hours ago', department: 'Sales' },
  { id: '3', employeeId: 'EMP-331', name: 'Emily Chen', sentimentScore: 68, riskScore: 31, lastActive: 'Just now', department: 'Marketing' },
  { id: '4', employeeId: 'EMP-087', name: 'Michael Chang', sentimentScore: 55, riskScore: 58, lastActive: '1 day ago', department: 'Engineering' },
  { id: '5', employeeId: 'EMP-552', name: 'Jessica Davis', sentimentScore: 92, riskScore: 14, lastActive: '5 mins ago', department: 'HR' },
];

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

function sentimentFromEntry(entry: Record<string, any>): 'positive' | 'neutral' | 'negative' {
  const raw = String(entry.sentiment ?? entry.label ?? entry.sentiment_label ?? '').toLowerCase();

  if (raw.includes('pos')) return 'positive';
  if (raw.includes('neg')) return 'negative';
  return 'neutral';
}

function sentimentSeriesFromMessages(messages: Array<Record<string, any>>): SentimentPoint[] {
  const grouped = new Map<string, { positive: number; neutral: number; negative: number }>();

  for (const message of messages) {
    const createdAt = new Date(message.created_at ?? new Date().toISOString());
    const key = createdAt.toISOString().slice(0, 10);
    const bucket = grouped.get(key) ?? { positive: 0, neutral: 0, negative: 0 };
    bucket[sentimentFromEntry(message)] += 1;
    grouped.set(key, bucket);
  }

  return Array.from(grouped.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, bucket]) => ({ date, ...bucket }));
}

async function safeSelect(table: string): Promise<Array<Record<string, any>>> {
  if (!supabase) {
    return [];
  }

  const { data, error } = await supabase.from(table).select('*').order('created_at', { ascending: false });
  if (error || !data) {
    return [];
  }

  return data as Array<Record<string, any>>;
}

function ticketStatusLabel(status: string): TicketStatus {
  const value = status.toLowerCase();
  if (value === 'resolved' || value === 'closed') return 'Resolved';
  if (value === 'escalated') return 'Escalated';
  if (value === 'in_progress') return 'In Review';
  return 'Open';
}

const API_BASE = () => (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000';

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
    }>;
    return rows.map((ticket, index) => ({
      id: String(ticket.id),
      employeeId: String(ticket.user_id).replace(/-/g, '').slice(0, 8).toUpperCase(),
      issue: ticket.query,
      against: ticket.category,
      status: ticketStatusLabel(String(ticket.status ?? 'open')),
      anonymous: false,
      createdAt: String(ticket.created_at ?? new Date().toISOString()),
      category: String(ticket.category ?? 'General'),
    }));
  } catch {
    return null;
  }
}

function scoreToPercent(score: number): number {
  return Math.max(0, Math.min(100, Math.round(((score + 1) / 2) * 100)));
}

function dateText(value?: string | null): string {
  if (!value) {
    return 'Recently';
  }

  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export async function loadDashboardData(): Promise<DashboardData> {
  const [apiTickets, messages, tickets, users, departments, risks, sentiments] = await Promise.all([
    fetchTicketsFromFastAPI(),
    safeSelect('messages'),
    safeSelect('tickets'),
    safeSelect('users'),
    safeSelect('departments'),
    safeSelect('attrition_risk'),
    safeSelect('sentiments'),
  ]);

  let mappedTickets: TicketRow[];
  if (apiTickets !== null) {
    mappedTickets = apiTickets;
  } else if (tickets.length) {
    mappedTickets = tickets.map((ticket, index) => ({
      id: String(ticket.id ?? `T-${index + 1}`),
      employeeId: String(ticket.user_id ?? ticket.employee_id ?? ticket.employeeId ?? 'EMP-000'),
      issue: String(ticket.query ?? ticket.issue ?? 'Employee request'),
      against: String(ticket.assigned_to ?? ticket.category ?? 'People Ops'),
      status: ticketStatusLabel(String(ticket.status ?? 'open')),
      anonymous: Boolean(ticket.anonymous ?? false),
      createdAt: String(ticket.created_at ?? new Date().toISOString()),
      category: String(ticket.category ?? 'General'),
    }));
  } else {
    mappedTickets = fallbackTickets;
  }

  const departmentMap = new Map<string, string>(
    (departments as BackendDepartmentRow[]).map((department) => [department.id, department.name])
  );
  const riskMap = new Map<string, number>(
    (risks as BackendRiskRow[]).map((risk) => [risk.user_id, Math.round(Number(risk.risk_score ?? 0) * 100)])
  );

  const latestSentimentMap = new Map<string, BackendSentimentRow>();
  for (const row of sentiments as BackendSentimentRow[]) {
    const existing = latestSentimentMap.get(row.user_id);
    if (!existing || new Date(row.created_at).getTime() > new Date(existing.created_at).getTime()) {
      latestSentimentMap.set(row.user_id, row);
    }
  }

  const mappedEmployees: EmployeeInsightRow[] = users.length
    ? (users as BackendUserRow[])
        .filter((user) => user.name)
        .map((user, index) => {
          const sentimentRow = latestSentimentMap.get(user.id);
          const sentimentScore = sentimentRow ? scoreToPercent(Number(sentimentRow.score ?? 0)) : 50;
          const riskScore = riskMap.get(user.id) ?? Math.max(0, 100 - sentimentScore);

          return {
            id: String(user.id ?? index + 1),
            employeeId: String(user.employee_id ?? `EMP-${index + 100}`),
            name: String(user.name ?? 'Employee'),
            sentimentScore,
            riskScore,
            lastActive: dateText(user.updated_at),
            department: user.department_id ? (departmentMap.get(user.department_id) ?? 'Unknown') : 'Unknown',
          };
        })
    : fallbackEmployees;

  const sentimentPoints = messages.length ? sentimentSeriesFromMessages(messages) : fallbackSentiment;
  const engagementScore = average(mappedEmployees.map((employee) => employee.sentimentScore));
  const openTickets = mappedTickets.filter((ticket) => ticket.status !== 'Resolved').length;
  const averageRisk = average(mappedEmployees.map((employee) => employee.riskScore));

  return {
    metrics: {
      engagementScore,
      riskLevel: riskLabel(averageRisk),
      openTickets,
      totalTickets: mappedTickets.length,
      aiSummary:
        'Sentiment is improving overall, but Engineering and Payroll are driving most of the open conversations. Use Mark to keep following up on leave requests and manager friction before they escalate.',
    },
    sentimentPoints,
    tickets: mappedTickets,
    employees: mappedEmployees,
  };
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