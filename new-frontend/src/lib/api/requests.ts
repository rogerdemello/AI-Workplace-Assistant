import { getJson, patchJson, postJson } from "@/lib/api/client";

export type RequestType = "appointment" | "expense" | "shift_change" | "document";

export type RequestStatus =
  | "pending"
  | "scheduled"
  | "approved"
  | "rejected"
  | "cancelled"
  | "completed";

/** Normalized row from `/api/v1/requests`. */
export interface EmployeeRequestRow {
  id: string;
  userId: string;
  requestType: RequestType;
  status: RequestStatus;
  title: string;
  details: Record<string, unknown>;
  scheduledAt: string | null;
  startDate: string | null;
  endDate: string | null;
  amount: number | null;
  hrNote: string | null;
  handledBy: string | null;
  handledAt: string | null;
  employeeName: string | null;
  createdAt: string;
}

export interface RequestSummary {
  pending: number;
  scheduled: number;
  approved: number;
  rejected: number;
  cancelled: number;
  completed: number;
  byType: Record<string, number>;
}

function mapRequestRecord(row: Record<string, unknown>): EmployeeRequestRow {
  const amount = row.amount;
  return {
    id: String(row.id ?? ""),
    userId: String(row.user_id ?? ""),
    requestType: (row.request_type as RequestType) ?? "document",
    status: (row.status as RequestStatus) ?? "pending",
    title: String(row.title ?? ""),
    details: (row.details as Record<string, unknown>) ?? {},
    scheduledAt: row.scheduled_at != null ? String(row.scheduled_at) : null,
    startDate: row.start_date != null ? String(row.start_date) : null,
    endDate: row.end_date != null ? String(row.end_date) : null,
    amount: amount != null && amount !== "" ? Number(amount) : null,
    hrNote: row.hr_note != null ? String(row.hr_note) : null,
    handledBy: row.handled_by != null ? String(row.handled_by) : null,
    handledAt: row.handled_at != null ? String(row.handled_at) : null,
    employeeName: row.employee_name != null ? String(row.employee_name) : null,
    createdAt: String(row.created_at ?? ""),
  };
}

export async function listRequests(filters?: {
  type?: RequestType;
  status?: RequestStatus;
  mineOnly?: boolean;
}): Promise<EmployeeRequestRow[]> {
  const params = new URLSearchParams();
  if (filters?.type) params.set("request_type", filters.type);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.mineOnly) params.set("mine_only", "true");
  const query = params.toString() ? `?${params.toString()}` : "";

  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/requests${query}`);
  if (!rows) return [];
  return rows.map(mapRequestRecord);
}

export async function getRequestSummary(): Promise<RequestSummary | null> {
  const row = await getJson<Record<string, unknown>>("/api/v1/requests/summary");
  if (!row) return null;
  return {
    pending: Number(row.pending ?? 0),
    scheduled: Number(row.scheduled ?? 0),
    approved: Number(row.approved ?? 0),
    rejected: Number(row.rejected ?? 0),
    cancelled: Number(row.cancelled ?? 0),
    completed: Number(row.completed ?? 0),
    byType: (row.by_type as Record<string, number>) ?? {},
  };
}

export async function approveRequest(
  requestId: string,
  hrNote?: string,
): Promise<EmployeeRequestRow | null> {
  const row = await patchJson<Record<string, unknown>>(
    `/api/v1/requests/${requestId}/approve`,
    hrNote ? { hr_note: hrNote } : {},
  );
  return row ? mapRequestRecord(row) : null;
}

export async function rejectRequest(
  requestId: string,
  hrNote?: string,
): Promise<EmployeeRequestRow | null> {
  const row = await patchJson<Record<string, unknown>>(
    `/api/v1/requests/${requestId}/reject`,
    hrNote ? { hr_note: hrNote } : {},
  );
  return row ? mapRequestRecord(row) : null;
}

/** Confirm (or move) an appointment slot. `scheduledAt` must be ISO-8601. */
export async function scheduleRequest(
  requestId: string,
  scheduledAt: string,
  hrNote?: string,
): Promise<EmployeeRequestRow | null> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/requests/${requestId}/schedule`, {
    scheduled_at: scheduledAt,
    ...(hrNote ? { hr_note: hrNote } : {}),
  });
  return row ? mapRequestRecord(row) : null;
}

export async function completeRequest(
  requestId: string,
  hrNote?: string,
): Promise<EmployeeRequestRow | null> {
  const row = await patchJson<Record<string, unknown>>(
    `/api/v1/requests/${requestId}/complete`,
    hrNote ? { hr_note: hrNote } : {},
  );
  return row ? mapRequestRecord(row) : null;
}

export async function cancelRequest(requestId: string): Promise<EmployeeRequestRow | null> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/requests/${requestId}/cancel`, {});
  return row ? mapRequestRecord(row) : null;
}

export async function createRequest(input: {
  requestType: RequestType;
  title: string;
  details?: Record<string, unknown>;
}): Promise<EmployeeRequestRow | null> {
  const row = await postJson<Record<string, unknown>>("/api/v1/requests", {
    request_type: input.requestType,
    title: input.title,
    details: input.details ?? {},
  });
  return row ? mapRequestRecord(row) : null;
}
