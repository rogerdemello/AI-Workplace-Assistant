import type { AuthSession } from "@/contexts/AuthContext";
import type { Priority, Ticket, TicketStatus } from "@/lib/domain-types";

const TICKET_STORAGE_KEY = "mark.dashboard.tickets";

export interface BackendTicketPayload {
  id: string;
  user_id?: string;
  query: string;
  category: string;
  status: string;
  priority: string;
  assigned_to?: string | null;
  created_at?: string;
  updated_at?: string;
  sla_due_at?: string | null;
}

interface LocalTicketInput {
  id: string;
  query: string;
  category: string;
  priority?: string;
  raisedBy?: string;
  assignedTo?: string;
  createdAt?: string;
  updatedAt?: string;
}

const slaHoursByPriority: Record<Priority, number> = {
  urgent: 12,
  high: 24,
  medium: 48,
  low: 72,
};

function toDateOnly(value?: string): string {
  if (!value) return new Date().toISOString().slice(0, 10);
  return value.slice(0, 10);
}

function toDashboardPriority(priority?: string): Priority {
  if (!priority) return "medium";
  if (priority === "critical") return "urgent";
  if (priority === "high" || priority === "medium" || priority === "low" || priority === "urgent") return priority;
  return "medium";
}

function toDashboardStatus(status?: string): TicketStatus {
  if (status === "open" || status === "in_progress" || status === "resolved" || status === "escalated") return status;
  if (status === "closed") return "resolved";
  return "open";
}

function toDashboardCategory(category?: string): Ticket["category"] {
  if (category === "leave" || category === "policy" || category === "complaint" || category === "payroll" || category === "it" || category === "wellbeing") {
    return category;
  }
  if (category === "benefits") return "policy";
  if (category === "it_support") return "it";
  return "policy";
}

function compactText(value: string, maxChars: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length <= maxChars ? normalized : `${normalized.slice(0, maxChars - 1)}…`;
}

function toSlaRemainingHours(priority: Priority, slaDueAt?: string | null): number {
  const total = slaHoursByPriority[priority];
  if (!slaDueAt) return total;
  const dueMs = Date.parse(slaDueAt);
  if (Number.isNaN(dueMs)) return total;
  return Math.max(0, Math.ceil((dueMs - Date.now()) / (1000 * 60 * 60)));
}

function buildDashboardTicket(input: {
  id: string;
  query: string;
  category?: string;
  status?: string;
  priority?: string;
  raisedBy?: string;
  assignedTo?: string;
  createdAt?: string;
  updatedAt?: string;
  slaDueAt?: string | null;
}): Ticket {
  const dashboardPriority = toDashboardPriority(input.priority);
  const slaHours = slaHoursByPriority[dashboardPriority];
  return {
    id: input.id,
    title: compactText(input.query, 44),
    summary: compactText(input.query, 96),
    category: toDashboardCategory(input.category),
    status: toDashboardStatus(input.status),
    priority: dashboardPriority,
    raisedBy: input.raisedBy || "employee-user",
    assignedTo: input.assignedTo,
    createdAt: toDateOnly(input.createdAt),
    updatedAt: toDateOnly(input.updatedAt || input.createdAt),
    slaHours,
    slaRemainingHours: toSlaRemainingHours(dashboardPriority, input.slaDueAt),
  };
}

export function mapBackendTicketToDashboardTicket(ticket: BackendTicketPayload): Ticket {
  return buildDashboardTicket({
    id: String(ticket.id),
    query: String(ticket.query || "Employee raised a support request"),
    category: ticket.category,
    status: ticket.status,
    priority: ticket.priority,
    raisedBy: ticket.user_id ? String(ticket.user_id) : undefined,
    assignedTo: ticket.assigned_to || undefined,
    createdAt: ticket.created_at,
    updatedAt: ticket.updated_at,
    slaDueAt: ticket.sla_due_at,
  });
}

function readStoredTickets(): Ticket[] {
  if (typeof window === "undefined") return [];
  try {
    const rawValue = window.localStorage.getItem(TICKET_STORAGE_KEY);
    if (!rawValue) return [];
    const parsed = JSON.parse(rawValue) as Ticket[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStoredTickets(tickets: Ticket[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TICKET_STORAGE_KEY, JSON.stringify(tickets));
}

export function loadLocalTickets(): Ticket[] {
  return readStoredTickets();
}

export function upsertLocalTicket(input: LocalTicketInput): Ticket {
  const newTicket = buildDashboardTicket({
    id: input.id,
    query: input.query,
    category: input.category,
    priority: input.priority,
    status: "open",
    raisedBy: input.raisedBy,
    assignedTo: input.assignedTo,
    createdAt: input.createdAt,
    updatedAt: input.updatedAt,
  });
  const currentTickets = readStoredTickets();
  const nextTickets = [newTicket, ...currentTickets.filter((ticket) => ticket.id !== newTicket.id)];
  writeStoredTickets(nextTickets);
  return newTicket;
}

export function mergeTickets(...groups: Ticket[][]): Ticket[] {
  const merged = new Map<string, Ticket>();
  groups.flat().forEach((ticket) => {
    merged.set(ticket.id, ticket);
  });
  return Array.from(merged.values()).sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

export function getReporterEmployeeId(session: AuthSession | null): string {
  if (session?.userId) return session.userId;
  return "anonymous";
}
