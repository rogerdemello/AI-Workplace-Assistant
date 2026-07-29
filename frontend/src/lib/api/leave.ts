import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, getJson, patchJson, readStoredSession } from "@/lib/api/client";

/** Normalized leave row from `/api/v1/leave`. */
export interface LeaveRow {
  id: string;
  userId: string;
  startDate: string;
  endDate: string;
  leaveType: string;
  reason: string | null;
  status: string;
  employeeName?: string | null;
  createdAt?: string;
}

function mapLeaveRecord(row: Record<string, unknown>): LeaveRow {
  return {
    id: String(row.id ?? ""),
    userId: String(row.user_id ?? ""),
    startDate: String(row.start_date ?? ""),
    endDate: String(row.end_date ?? ""),
    leaveType: String(row.leave_type ?? "paid"),
    reason: row.reason != null ? String(row.reason) : null,
    status: String(row.status ?? "pending"),
    employeeName: row.employee_name != null ? String(row.employee_name) : null,
    createdAt: row.created_at ? String(row.created_at) : undefined,
  };
}

export async function listLeaveRequests(statusFilter?: string): Promise<LeaveRow[]> {
  const q = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  const rows = await getJson<Array<Record<string, unknown>>>(`/api/v1/leave${q}`);
  if (!rows) return [];
  return rows.map(mapLeaveRecord);
}

export async function approveLeaveRequest(leaveId: string, reviewComment?: string): Promise<LeaveRow | null> {
  const body = reviewComment ? { review_comment: reviewComment } : {};
  const row = await patchJson<Record<string, unknown>>(`/api/v1/leave/${leaveId}/approve`, body);
  return row ? mapLeaveRecord(row) : null;
}

export async function rejectLeaveRequest(leaveId: string, reviewComment?: string): Promise<LeaveRow | null> {
  const body = reviewComment ? { review_comment: reviewComment } : {};
  const row = await patchJson<Record<string, unknown>>(`/api/v1/leave/${leaveId}/reject`, body);
  return row ? mapLeaveRecord(row) : null;
}

export async function cancelLeaveRequest(leaveId: string): Promise<LeaveRow | null> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/leave/${leaveId}/cancel`, {});
  return row ? mapLeaveRecord(row) : null;
}

export type LeaveTypeApi = "paid" | "sick" | "work_from_home" | "unpaid";

export async function createLeaveRequest(input: {
  startDate: string;
  endDate: string;
  leaveType: LeaveTypeApi;
  reason?: string;
}): Promise<{ ok: true; leave: LeaveRow; overlapWarning: string | null } | { ok: false; error: string }> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return { ok: false, error: "Not signed in." };
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/leave`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        start_date: input.startDate,
        end_date: input.endDate,
        leave_type: input.leaveType,
        reason: input.reason?.trim() || null,
      }),
    });
    const overlapWarning = response.headers.get("X-Leave-Overlap-Warning");
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const errBody = (await response.json()) as { detail?: unknown };
        if (typeof errBody.detail === "string") message = errBody.detail;
        else if (Array.isArray(errBody.detail)) message = errBody.detail.map((d) => JSON.stringify(d)).join("; ");
      } catch {
        // Ignore response parse errors from failed leave request.
      }
      return { ok: false, error: message };
    }
    const data = (await response.json()) as Record<string, unknown>;
    return { ok: true, leave: mapLeaveRecord(data), overlapWarning };
  } catch {
    return { ok: false, error: "Network error." };
  }
}
