import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, getJson, patchJson, readStoredSession } from "@/lib/api/client";

export interface RagDocumentRow {
  id: string;
  title: string;
  is_active: boolean;
  created_at: string;
  chunks_count: number;
}

export async function listRagDocuments(): Promise<RagDocumentRow[]> {
  const rows = await getJson<Array<Record<string, unknown>>>("/api/v1/rag/documents");
  if (!rows) return [];
  return rows.map((row) => ({
    id: String(row.id ?? ""),
    title: String(row.title ?? "Untitled"),
    is_active: Boolean(row.is_active),
    created_at: String(row.created_at ?? ""),
    chunks_count: Number(row.chunks_count ?? 0),
  }));
}

export async function uploadRagDocument(file: File, title?: string): Promise<{ ok: boolean; error?: string }> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return { ok: false, error: "Not authenticated" };
  const form = new FormData();
  form.append("file", file);
  if (title?.trim()) form.append("title", title.trim());

  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/rag/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!response.ok) {
      const text = await response.text();
      return { ok: false, error: text || "Upload failed" };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Upload failed" };
  }
}

export async function setRagDocumentActive(documentId: string, isActive: boolean): Promise<boolean> {
  const row = await patchJson<Record<string, unknown>>(`/api/v1/rag/documents/${documentId}/active?is_active=${isActive}`, {});
  return Boolean(row);
}

export async function deleteRagDocument(documentId: string): Promise<boolean> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return false;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/rag/documents/${documentId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return false;
    const body = (await response.json()) as { ok?: boolean };
    return Boolean(body.ok);
  } catch {
    return false;
  }
}
