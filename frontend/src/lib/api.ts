/**
 * HR Platform API Client
 * Typed fetch wrappers for backend API endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  assigned_to?: string;
}

/** Full ticket response from backend */
export interface TicketResponse {
  id: string;
  user_id: string;
  query: string;
  category: string;
  status: TicketStatus;
  priority: TicketPriority;
  assigned_to?: string;
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

/**
 * Get authentication headers with auto-login for demo mode
 */
const getAuthHeaders = async (): Promise<HeadersInit> => {
  let token = localStorage.getItem('auth_token');
  
  if (!token) {
    try {
      const loginRes = await fetch(`${API_BASE_URL}/api/v1/demo/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Demo User', email: 'demo@example.com' })
      });
      if (loginRes.ok) {
        const loginData = await loginRes.json();
        token = loginData.access_token as string;
        localStorage.setItem('auth_token', token);
      }
    } catch (e) {
      console.error('Demo login failed:', e);
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
