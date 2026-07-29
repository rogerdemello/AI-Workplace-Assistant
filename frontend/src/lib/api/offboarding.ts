import { apiBaseUrl, getJson, readStoredSession } from "@/lib/api/client";
import { ensureSessionToken } from "@/lib/chat-api";

export interface OffboardingTask {
  id: string;
  user_id: string;
  title: string;
  kind: string;
  completed: boolean;
  completed_at: string | null;
  due_date: string | null;
  notes: string | null;
  assigned_to: string | null;
}

export async function listOffboardingTasks(userId: string): Promise<OffboardingTask[]> {
  const rows = await getJson<OffboardingTask[]>(`/api/v1/users/${userId}/offboarding-tasks`);
  return Array.isArray(rows) ? rows : [];
}

export async function patchOffboardingTask(
  taskId: string,
  patch: Partial<Pick<OffboardingTask, "completed" | "notes">>,
): Promise<OffboardingTask | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/offboarding-tasks/${taskId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(patch),
    });
    if (!response.ok) return null;
    return (await response.json()) as OffboardingTask;
  } catch {
    return null;
  }
}
