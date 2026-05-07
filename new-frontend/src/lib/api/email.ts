import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, postJson, readStoredSession } from "@/lib/api/client";

const EMAIL_TYPES = ["general", "follow_up", "leave_request", "complaint", "resignation"] as const;
const TONE_MAP: Record<string, string> = {
  Warm: "friendly",
  Direct: "neutral",
  Empathetic: "friendly",
  Formal: "formal",
  Brief: "neutral",
};

export async function draftEmail(input: { context: string; toneLabel: string }): Promise<{ subject: string; body: string } | null> {
  const apiTone = TONE_MAP[input.toneLabel] || "friendly";
  const type = EMAIL_TYPES.find((t) => input.context.toLowerCase().includes(t.replace("_", " "))) ?? "general";
  const res = await postJson<Record<string, unknown>>("/api/v1/email/draft", {
    type,
    tone: apiTone,
    context: { message: input.context },
  });
  if (!res) return null;
  return {
    subject: String(res.subject ?? "Draft"),
    body: String(res.body ?? ""),
  };
}

export async function sendEmail(input: {
  to: string;
  subject: string;
  body: string;
  cc?: string[];
}): Promise<{ ok: true; detail: string } | { ok: false; error: string }> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return { ok: false, error: "Not signed in." };
  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/email/send`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        to: input.to,
        subject: input.subject,
        body: input.body,
        cc: input.cc ?? [],
      }),
    });
    const data = (await response.json()) as Record<string, unknown>;
    if (!response.ok) {
      return {
        ok: false,
        error: typeof data.detail === "string" ? data.detail : "Could not send email. Check SMTP configuration.",
      };
    }
    return {
      ok: true,
      detail: String(data.detail ?? "Email sent."),
    };
  } catch {
    return { ok: false, error: "Could not send email. Check API availability and SMTP configuration." };
  }
}
