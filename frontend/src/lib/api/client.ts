import { ensureSessionToken } from "@/lib/chat-api";
import type { AuthSession } from "@/contexts/AuthContext";

export function apiBaseUrl(): string {
  const envValue =
    (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
    (typeof import.meta !== "undefined" && import.meta.env?.NEXT_PUBLIC_API_URL);
  return String(envValue || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export function readStoredSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const rawSession = window.localStorage.getItem("mark.auth.session");
    if (!rawSession) return null;
    return JSON.parse(rawSession) as AuthSession;
  } catch {
    return null;
  }
}

/**
 * Extract a human-friendly error message from a failed fetch Response.
 * Backend FastAPI errors typically come back as `{ detail: "..." }` or `{ detail: [{loc, msg}] }`.
 */
export async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const ct = response.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      const body = (await response.json()) as Record<string, unknown>;
      const detail = body?.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0] as Record<string, unknown>;
        return String(first.msg ?? "Request failed.");
      }
      if (body?.message && typeof body.message === "string") return body.message;
    }
    const text = await response.text();
    return text.slice(0, 200) || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

export async function getJson<T>(path: string): Promise<T | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function postJson<T>(path: string, body: unknown): Promise<T | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function patchJson<T>(path: string, body: unknown = {}): Promise<T | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function deleteJson<T>(path: string): Promise<T | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) return null;
    if (response.status === 204) return {} as T;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function subscribeToSse(
  path: string,
  handlers: {
    onEvent: (eventType: string, payload: Record<string, unknown>) => void;
    onError?: (error: unknown) => void;
  },
): () => void {
  const controller = new AbortController();
  let active = true;

  const run = async () => {
    const token = await ensureSessionToken(readStoredSession());
    if (!token || !active) return;
    try {
      const response = await fetch(`${apiBaseUrl()}${path}`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "text/event-stream",
        },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const handleBlock = (block: string) => {
        const lines = block
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
        if (!lines.length) return;
        const eventLine = lines.find((line) => line.startsWith("event:"));
        const dataLine = lines.find((line) => line.startsWith("data:"));
        if (!dataLine) return;
        const eventType = eventLine ? eventLine.slice("event:".length).trim() : "message";
        const dataRaw = dataLine.slice("data:".length).trim();
        try {
          const payload = JSON.parse(dataRaw) as Record<string, unknown>;
          handlers.onEvent(eventType, payload);
        } catch (error) {
          handlers.onError?.(error);
        }
      };

      while (active) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        blocks.forEach(handleBlock);
      }

      if (buffer.trim()) handleBlock(buffer.trim());
    } catch (error) {
      if (!controller.signal.aborted) handlers.onError?.(error);
    }
  };

  void run();
  return () => {
    active = false;
    controller.abort();
  };
}
