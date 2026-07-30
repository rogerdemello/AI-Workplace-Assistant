import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, getJson, readStoredSession } from "@/lib/api/client";

export interface WhatsappLinkIssue {
  code: string;
  expires_at: string;
  ttl_minutes: number;
  instructions: string;
}

export interface WhatsappLinkStatus {
  status: "unlinked" | "pending" | "linked";
  phone_masked: string | null;
  linked_at: string | null;
  pending_code: string | null;
  expires_at: string | null;
}

export async function getWhatsappLinkStatus(): Promise<WhatsappLinkStatus | null> {
  return getJson<WhatsappLinkStatus>("/api/v1/whatsapp/link/status");
}

export async function startWhatsappLink(): Promise<WhatsappLinkIssue | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/whatsapp/link/start`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as WhatsappLinkIssue;
  } catch {
    return null;
  }
}

export async function unlinkWhatsapp(): Promise<boolean> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return false;
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/whatsapp/link`, {
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
