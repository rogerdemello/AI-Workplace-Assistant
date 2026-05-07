/**
 * HR Platform API Client
 * Typed fetch wrappers for backend API endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let validatedAuthToken: string | null = null;

// ============================================================================
// Types - Matching Backend Schemas
// ============================================================================

/** KPI metrics from analytics overview endpoint */
export interface KPIResponse {
  engagement_score: number;
  resolution_rate: number;
  avg_response_time: number;
  active_users: number;
  total_tickets: number;
  open_tickets?: number;
}

/** Single sentiment trend data point */
export interface SentimentTrendResponse {
  date: string;
  positive: number;
  neutral: number;
  negative: number;
}

/** Ticket status enum */
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'escalated' | 'closed';

/** Ticket priority enum */
export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';

/** Ticket creation request */
export interface TicketCreate {
  query: string;
  category: string;
  priority?: TicketPriority;
}

/** Ticket update request */
export interface TicketUpdate {
  status?: TicketStatus;
  priority?: TicketPriority;
  assigned_to?: string | null;
}

/** Full ticket response from backend */
export interface TicketResponse {
  id: string;
  user_id: string;
  query: string;
  category: string;
  status: TicketStatus;
  priority: TicketPriority;
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  sla_due_at?: string;
  sla_warning: boolean;
}

/** Email draft request */
export interface EmailDraftRequest {
  type: string;
  tone: string;
  context?: Record<string, unknown>;
}

/** Email draft response */
export interface EmailDraftResponse {
  subject: string;
  body: string;
  tone: string;
  type: string;
  context: Record<string, unknown>;
}

/** API error response */
export interface ApiError {
  detail: string;
}

// ============================================================================
// Auth Utilities
// ============================================================================

async function isTokenValid(token: string): Promise<boolean> {
  if (validatedAuthToken === token) {
    return true;
  }

  try {
    const meRes = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!meRes.ok) {
      return false;
    }
    validatedAuthToken = token;
    return true;
  } catch {
    return false;
  }
}

const getAuthHeaders = async (): Promise<HeadersInit> => {
  let token = localStorage.getItem('auth_token');

  if (token) {
    const ok = await isTokenValid(token);
    if (!ok) {
      localStorage.removeItem('auth_token');
      validatedAuthToken = null;
      token = null;
    }
  }

  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

/**
 * Clear auth token to force re-login
 */
export const clearAuth = (): void => {
  localStorage.removeItem('auth_token');
  validatedAuthToken = null;
};

// ============================================================================
// Analytics API
// ============================================================================

/**
 * Get analytics overview with KPI metrics
 * @param departmentId - Optional department UUID filter
 * @returns KPI data including engagement, resolution rate, response time
 */
export async function getAnalyticsOverview(departmentId?: string): Promise<KPIResponse> {
  const headers = await getAuthHeaders();
  const params = departmentId ? `?department_id=${departmentId}` : '';
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/overview${params}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch analytics overview' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Get sentiment trend data over time
 * @param days - Number of days to look back (max 90)
 * @returns Array of sentiment trend data points
 */
export async function getSentimentTrend(days: number = 30): Promise<SentimentTrendResponse[]> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/sentiment?days=${Math.min(days, 90)}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch sentiment trend' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/** Burnout risk data for a user or department */
export interface BurnoutRiskResponse {
  user_id: string;
  name: string;
  risk_score: number;
  risk_level: string;
  factors: Record<string, number>;
}

/** Burnout summary for a department or org */
export interface BurnoutSummaryResponse {
  risk_scores: BurnoutRiskResponse[];
  average_risk: number;
  high_risk_count: number;
  medium_risk_count: number;
}

/**
 * Get burnout risk summary for department or org
 */
export async function getBurnoutRisk(departmentId?: string): Promise<BurnoutSummaryResponse> {
  const headers = await getAuthHeaders();
  const params = departmentId ? `?department_id=${departmentId}` : '';
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/burnout${params}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch burnout risk' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Get burnout risk for a specific user
 */
export async function getUserBurnoutRisk(userId: string): Promise<BurnoutRiskResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/burnout/${userId}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch user burnout risk' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/** Executive dashboard response */
export interface ExecutiveDashboardResponse {
  org_health_score: number;
  burnout_risk_pct: number;
  attrition_risk_pct: number;
  enps: number;
  engagement_trend: { date: string; score: number }[];
  top_risks: { type: string; user_id: string; name: string; risk_score: number }[];
  recommendations: string[];
}

/**
 * Get executive dashboard with org-wide analytics
 */
export async function getExecutiveDashboard(): Promise<ExecutiveDashboardResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/executive`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch executive dashboard' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/** AI-generated insight */
export interface InsightResponse {
  id: string;
  insight_type: string;
  title: string;
  description: string;
  severity: string;
  affected_entity_type: string | null;
  affected_entity_id: string | null;
  metrics: Record<string, unknown>;
  recommendations: string[];
  is_resolved: boolean;
  created_at: string;
}

/**
 * Get AI-generated insights
 */
export async function getInsights(limit: number = 20, includeResolved: boolean = false): Promise<InsightResponse[]> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/analytics/insights?limit=${limit}&include_resolved=${includeResolved}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch insights' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

// ============================================================================
// Tickets API
// ============================================================================

/**
 * Get all tickets for current user (or all if HR/admin)
 * @param status - Optional status filter
 * @returns Array of tickets
 */
export async function getTickets(status?: TicketStatus): Promise<TicketResponse[]> {
  const headers = await getAuthHeaders();
  const params = status ? `?status=${status}` : '';
  
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets${params}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch tickets' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Create a new support ticket
 * @param ticket - Ticket creation data
 * @returns Created ticket
 */
export async function createTicket(ticket: TicketCreate): Promise<TicketResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets`, {
    method: 'POST',
    headers,
    body: JSON.stringify(ticket)
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to create ticket' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Update an existing ticket
 * @param ticketId - UUID of ticket to update
 * @param updates - Fields to update
 * @returns Updated ticket
 */
export async function updateTicket(ticketId: string, updates: TicketUpdate): Promise<TicketResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets/${ticketId}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(updates)
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to update ticket' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Get a single ticket by ID
 * @param ticketId - UUID of ticket to fetch
 * @returns Ticket details
 */
export async function getTicket(ticketId: string): Promise<TicketResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets/${ticketId}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to fetch ticket' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

export interface TicketMessageResponse {
  id: string;
  ticket_id: string;
  sender_id?: string;
  message_text: string;
  created_at: string;
}

export interface TicketAssigneeResponse {
  id: string;
  name: string;
  email: string;
  role: 'hr' | 'admin' | string;
}

export async function getTicketAssignees(): Promise<TicketAssigneeResponse[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets/assignees`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load ticket assignees' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function listTicketMessages(ticketId: string): Promise<TicketMessageResponse[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets/${ticketId}/messages`, {
    method: 'GET',
    headers,
  });
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load messages' }));
    throw new Error(error.detail);
  }
  return response.json();
}

export async function addTicketMessage(ticketId: string, messageText: string): Promise<TicketMessageResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/tickets/${ticketId}/messages`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message_text: messageText }),
  });
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to add message' }));
    throw new Error(error.detail);
  }
  return response.json();
}

export interface HrAlertItem {
  id: string;
  title: string;
  body: string | null;
  severity: string;
  alert_type: string | null;
  source: string;
  created_at: string;
  acknowledged: boolean;
}

export async function listHrAlerts(limit = 50): Promise<HrAlertItem[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/alerts?limit=${limit}`, { method: 'GET', headers });
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load alerts' }));
    throw new Error(error.detail);
  }
  return response.json();
}

export async function runHrAlertScan(): Promise<{ ok: boolean; alerts_stored?: number; error?: string }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/alerts/run-scan`, { method: 'POST', headers });
  return response.json();
}

// ============================================================================
// Email API
// ============================================================================

/**
 * Draft an email using AI
 * @param request - Email draft request with type, tone, and context
 * @returns Generated email draft
 */
export async function draftEmail(request: EmailDraftRequest): Promise<EmailDraftResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/email/draft`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request)
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to draft email' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

// ============================================================================
// Email Types and Tones (for type safety)
// ============================================================================

/** Supported email types for draftEmail */
export const EMAIL_TYPES = [
  'leave_request',
  'resignation',
  'feedback',
  'complaint',
  'appreciation',
  'general'
] as const;

export type EmailType = typeof EMAIL_TYPES[number];

/** Supported tones for draftEmail */
export const EMAIL_TONES = [
  'formal',
  'professional',
  'friendly',
  'empathetic',
  'direct'
] as const;

export type EmailTone = typeof EMAIL_TONES[number];

// ============================================================================
// Leave Management API
// ============================================================================

/** Leave request status */
export type LeaveStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';

/** Leave request response */
export interface LeaveRequestResponse {
  id: string;
  employee_id: string;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason?: string;
  status: LeaveStatus;
  created_at: string;
  updated_at?: string;
}

/**
 * Get all leave requests with optional status filter
 * @param status - Optional status filter
 * @returns Array of leave requests
 */
export async function getLeaveRequests(status?: string): Promise<LeaveRequestResponse[]> {
  const headers = await getAuthHeaders();
  const params = status ? `?status=${status}` : '';
  
  const response = await fetch(`${API_BASE_URL}/api/v1/leave${params}`, {
    method: 'GET',
    headers
  });
  
  if (!response.ok) {
    return [];
  }
  
  return response.json();
}

/**
 * Approve a leave request
 * @param leaveId - UUID of leave request to approve
 * @returns Updated leave request
 */
export async function approveLeave(leaveId: string): Promise<LeaveRequestResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/leave/${leaveId}/approve`, {
    method: 'PATCH',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to approve leave' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Reject a leave request
 * @param leaveId - UUID of leave request to reject
 * @returns Updated leave request
 */
export async function rejectLeave(leaveId: string): Promise<LeaveRequestResponse> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/api/v1/leave/${leaveId}/reject`, {
    method: 'PATCH',
    headers
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to reject leave' }));
    throw new Error(error.detail);
  }
  
  return response.json();
}

/**
 * Cancel a pending leave request (employee action)
 * @param leaveId - UUID of leave request to cancel
 * @returns Updated leave request
 */
export async function cancelLeave(leaveId: string): Promise<LeaveRequestResponse> {
  const headers = await getAuthHeaders();

  const response = await fetch(`${API_BASE_URL}/api/v1/leave/${leaveId}/cancel`, {
    method: 'PATCH',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to cancel leave request' }));
    throw new Error(error.detail);
  }

  return response.json();
}

// ============================================================================
// Wellbeing API
// ============================================================================

export type WellbeingReminderStatus = 'active' | 'paused' | 'cancelled';
export type WellbeingScheduleKind = 'one_time' | 'daily' | 'weekly' | 'cron';

export interface WellbeingReminderResponse {
  id: string;
  reminder_type: string;
  title: string;
  message: string;
  schedule_kind: WellbeingScheduleKind;
  run_at?: string | null;
  cron_expr?: string | null;
  timezone: string;
  status: WellbeingReminderStatus;
  next_trigger_at?: string | null;
  last_triggered_at?: string | null;
  created_at: string;
}

export interface CreateWellbeingReminderInput {
  reminder_type: string;
  title: string;
  message: string;
  schedule_kind: WellbeingScheduleKind;
  run_at?: string;
  cron_expr?: string;
  timezone?: string;
  payload?: Record<string, unknown>;
}

export interface UpdateWellbeingReminderInput {
  title?: string;
  message?: string;
  status?: WellbeingReminderStatus;
  schedule_kind?: WellbeingScheduleKind;
  run_at?: string;
  cron_expr?: string;
  timezone?: string;
  next_trigger_at?: string;
  payload?: Record<string, unknown>;
}

export type DailyCheckinMood = 'great' | 'good' | 'okay' | 'low' | 'stressed';

export interface DailyCheckinInput {
  mood: DailyCheckinMood;
  message?: string;
  wants_followup?: boolean;
}

export interface DailyCheckinResponse {
  mood: string;
  signal: {
    triage_level?: string;
    sentiment_label?: string;
    sentiment_score?: number;
    stress_indicator?: number;
    burnout_indicator?: number;
    requires_hr_followup?: boolean;
    [key: string]: unknown;
  };
  suggested_next_step: string;
}

export interface WellbeingHighRiskEmployee {
  user_id: string;
  name: string;
  mood_score: number;
  risk_score: number;
  risk_level: string;
  open_tickets: number;
  last_active: string;
  reasons: string[];
}

export interface WellbeingWeeklySummary {
  window_days: number;
  high_risk_employees: number;
  followup_signals: number;
  open_tickets: number;
  avg_engagement_score: number;
  top_issues: Array<{ category?: string; count?: number }>;
}

export async function getWellbeingReminders(includeCancelled = false): Promise<WellbeingReminderResponse[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_BASE_URL}/api/v1/wellbeing/reminders?include_cancelled=${includeCancelled ? 'true' : 'false'}`,
    {
      method: 'GET',
      headers,
    }
  );

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load reminders' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function createWellbeingReminder(payload: CreateWellbeingReminderInput): Promise<WellbeingReminderResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/reminders`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to create reminder' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function updateWellbeingReminder(
  reminderId: string,
  updates: UpdateWellbeingReminderInput
): Promise<WellbeingReminderResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/reminders/${reminderId}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to update reminder' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function cancelWellbeingReminder(reminderId: string): Promise<void> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/reminders/${reminderId}`, {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to cancel reminder' }));
    throw new Error(error.detail);
  }
}

export async function submitDailyCheckin(payload: DailyCheckinInput): Promise<DailyCheckinResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/check-ins/daily`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      mood: payload.mood,
      message: payload.message || '',
      wants_followup: payload.wants_followup ?? false,
    }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to submit daily check-in' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function getHighRiskEmployees(limit = 25): Promise<WellbeingHighRiskEmployee[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/high-risk?limit=${Math.max(1, Math.min(limit, 100))}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load high-risk employees' }));
    throw new Error(error.detail);
  }

  return response.json();
}

export async function getWellbeingWeeklySummary(): Promise<WellbeingWeeklySummary> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/wellbeing/weekly-summary`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load weekly wellbeing summary' }));
    throw new Error(error.detail);
  }

  return response.json();
}

// ============================================================================
// Employee Scores API
// ============================================================================

export interface EmployeeScore {
  user_id: string;
  name: string;
  email: string;
  department: string | null;
  mental_health: number;
  sentiment: number;
  engagement: number;
  risk: number;
  status: 'healthy' | 'stable' | 'at_risk' | 'struggling' | 'critical';
}

export interface EmployeeScoresResponse {
  scores: EmployeeScore[];
  org_average: number;
  risk_alerts: Array<{
    user_id: string;
    name: string;
    mental_health: number;
    status: string;
    alert_id: string | null;
  }>;
}

export async function getEmployeeScores(limit = 50, includeAlerts = true): Promise<EmployeeScoresResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_BASE_URL}/api/v1/employees/scores?limit=${limit}&include_alerts=${includeAlerts}`,
    { method: 'GET', headers }
  );

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load employee scores' }));
    throw new Error(error.detail);
  }

  return response.json();
}

// ============================================================================
// Appreciation API
// ============================================================================

export interface AppreciationResponse {
  id: string;
  from_user_id: string | null;
  to_user_id: string;
  message: string;
  is_anonymous: boolean;
  created_at: string;
  to_user_name?: string;
  from_user_name?: string;
}

/**
 * Get all appreciation notes (HR/admin only)
 */
export async function getAllAppreciations(limit = 50): Promise<AppreciationResponse[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/appreciation?limit=${limit}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load appreciations' }));
    throw new Error(error.detail);
  }

  return response.json();
}

/**
 * Get appreciation notes for a specific user
 */
export async function getUserAppreciations(userId: string, limit = 20): Promise<AppreciationResponse[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/api/v1/appreciation/user/${userId}?limit=${limit}`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'Failed to load user appreciations' }));
    throw new Error(error.detail);
  }

  return response.json();
}
