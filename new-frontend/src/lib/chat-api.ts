import type { AuthSession } from "@/contexts/AuthContext";
import type { FlowMetadata } from "@/types/chat";
import { getReporterEmployeeId, upsertLocalTicket } from "@/lib/ticket-store";

interface BackendUnifiedChatResponse {
  response?: string;
  intent?: string;
  sentiment?: string;
  conversation_id?: string;
  context?: Record<string, unknown>;
  conversation_state?: Record<string, unknown>;
  flow_metadata?: FlowMetadata | null;
  completed?: boolean;
}

export interface ChatBridgeResponse {
  reply: string;
  state: {
    conversationId?: string;
    intent?: string;
    sentiment?: string;
    context?: Record<string, unknown>;
    conversationState?: Record<string, unknown>;
    flowMetadata?: FlowMetadata | null;
    completed?: boolean;
  };
}

export interface ChatAttachmentMeta {
  name: string;
  size: number;
}

export interface MemoryCardResponse {
  title?: string;
  summary?: string;
  tags?: string[];
  last_updated?: string;
}

/** Dispatched when `auth_token` is rejected by `/auth/me` (401/403) so UI can logout without spamming retries. */
export const MARK_AUTH_INVALID_EVENT = "mark-auth-invalid";

function apiBaseUrl(): string {
  const envValue =
    (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
    (typeof import.meta !== "undefined" && import.meta.env?.NEXT_PUBLIC_API_URL);
  return String(envValue || "http://127.0.0.1:8000").replace(/\/$/, "");
}

/** Deduplicates concurrent `/auth/me` probes (was causing bursts of duplicate 401s). */
const inflightTokenVerify = new Map<string, Promise<boolean>>();

async function verifyAuthTokenWithBackend(token: string): Promise<boolean> {
  let pending = inflightTokenVerify.get(token);
  if (pending) {
    return pending;
  }
  pending = (async (): Promise<boolean> => {
    try {
      const meResponse = await fetch(`${apiBaseUrl()}/api/v1/auth/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meResponse.status === 401 || meResponse.status === 403) {
        if (
          typeof window !== "undefined" &&
          window.localStorage.getItem("auth_token") === token
        ) {
          window.localStorage.removeItem("auth_token");
        }
        window.dispatchEvent(new CustomEvent(MARK_AUTH_INVALID_EVENT, { detail: { status: meResponse.status } }));
        return false;
      }
      return meResponse.ok;
    } catch {
      /* Network glitch — do not clear token here */
      return false;
    } finally {
      inflightTokenVerify.delete(token);
    }
  })();
  inflightTokenVerify.set(token, pending);
  return pending;
}

/** Runs once after load so stale JWT + restored session logout together. Safe to fire-and-forget. */
export async function verifyStoredCredentialOnce(): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }
  const token = window.localStorage.getItem("auth_token");
  if (!token) {
    return;
  }
  await verifyAuthTokenWithBackend(token);
}

function normalizeFlowMetadata(raw: unknown): FlowMetadata | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  return {
    flow_name: (o.flow_name as string | null) ?? null,
    intent: (o.intent as string | null) ?? undefined,
    step: (o.step as string | null) ?? undefined,
    missing_fields: Array.isArray(o.missing_fields) ? (o.missing_fields as string[]) : [],
    collected_fields: Array.isArray(o.collected_fields) ? (o.collected_fields as string[]) : [],
    completed: Boolean(o.completed),
  };
}

async function getTokenForSession(_session: AuthSession | null): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }

  const existingToken = window.localStorage.getItem("auth_token");
  if (!existingToken) {
    return null;
  }
  const ok = await verifyAuthTokenWithBackend(existingToken);
  return ok ? existingToken : null;
}

/** Creates a server conversation and returns MARK's proactive first message (employee chat). */
export async function startChatSession(session: AuthSession | null): Promise<{ conversationId: string; greeting: string } | null> {
  const token = await getTokenForSession(session);
  if (!token) {
    return null;
  }
  try {
    const res = await fetch(`${apiBaseUrl()}/api/v1/chat/conversations/start`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      return null;
    }
    const data = (await res.json()) as { conversation_id?: string; greeting?: string };
    const conversationId = data.conversation_id ? String(data.conversation_id) : "";
    const greeting = String(data.greeting || "").trim();
    if (!conversationId || !greeting) {
      return null;
    }
    return { conversationId, greeting };
  } catch {
    return null;
  }
}

export async function ensureSessionToken(session: AuthSession | null): Promise<string | null> {
  return getTokenForSession(session);
}

/** Best-effort close of a server conversation when the user starts a new chat. */
export async function closeConversation(conversationId: string, session: AuthSession | null): Promise<boolean> {
  const id = conversationId?.trim();
  if (!id) {
    return false;
  }
  const token = await getTokenForSession(session);
  if (!token) {
    return false;
  }
  try {
    const res = await fetch(`${apiBaseUrl()}/api/v1/chat/conversations/${encodeURIComponent(id)}/close`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function requestChatReply(
  input: { message: string; conversationId?: string; attachment?: ChatAttachmentMeta | null },
  session: AuthSession | null,
  options?: { onPartial?: (text: string) => void },
): Promise<ChatBridgeResponse | null> {
  const token = await getTokenForSession(session);
  if (!token) {
    return null;
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  const contentWithAttachment = input.attachment
    ? `${input.message}\n\n[Attached file: ${input.attachment.name} (${Math.max(1, Math.round(input.attachment.size / 1024))} KB)]`
    : input.message;

  /** Only the streaming step is aborted; `/conversations/start` can take 20–30s+ and must not share this timer. */
  const streamTimeoutMs = Math.max(15000, Number(import.meta.env?.VITE_CHAT_STREAM_TIMEOUT_MS || 120000));

  const mapUnifiedToBridge = (data: BackendUnifiedChatResponse, conversationId: string): ChatBridgeResponse => ({
    reply: data.response || "I could not generate a response right now.",
    state: {
      conversationId,
      intent: data.intent,
      sentiment: data.sentiment,
      context: data.context,
      conversationState: data.conversation_state,
      flowMetadata: normalizeFlowMetadata(data.flow_metadata),
      completed: Boolean(data.completed),
    },
  });

  const startConversation = async (): Promise<string | undefined> => {
    const startResponse = await fetch(`${apiBaseUrl()}/api/v1/chat/conversations/start`, {
      method: "POST",
      headers,
    });
    if (!startResponse.ok) {
      return undefined;
    }
    const startData = (await startResponse.json()) as { conversation_id?: string };
    return startData.conversation_id ? String(startData.conversation_id) : undefined;
  };

  type StreamAttempt = { kind: "reply"; value: ChatBridgeResponse } | { kind: "stale" } | { kind: "fallback" };

  const tryStreamingTurn = async (conversationId: string, streamAbort: AbortController): Promise<StreamAttempt> => {
    const streamResponse = await fetch(`${apiBaseUrl()}/api/v1/chat/conversations/${conversationId}/respond/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message: contentWithAttachment }),
      signal: streamAbort.signal,
    });

    if (streamResponse.status === 404) {
      return { kind: "stale" };
    }

    if (!(streamResponse.ok && streamResponse.body)) {
      return { kind: "fallback" };
    }

    const reader = streamResponse.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamedReply = "";
    let donePayload: Record<string, unknown> | null = null;

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
        if (eventType === "token") {
          streamedReply = String(payload.text ?? streamedReply);
          options?.onPartial?.(streamedReply);
        } else if (eventType === "done") {
          donePayload = payload;
        }
      } catch {
        // Ignore malformed event payloads.
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      blocks.forEach(handleBlock);
    }
    if (buffer.trim()) {
      handleBlock(buffer.trim());
    }

    if (donePayload) {
      return {
        kind: "reply",
        value: {
          reply: String(donePayload.response ?? streamedReply ?? "I could not generate a response right now."),
          state: {
            conversationId,
            intent: donePayload.intent ? String(donePayload.intent) : undefined,
            sentiment: donePayload.sentiment ? String(donePayload.sentiment) : undefined,
            context: (donePayload.context as Record<string, unknown>) || undefined,
            conversationState: (donePayload.conversation_state as Record<string, unknown>) || undefined,
            flowMetadata: normalizeFlowMetadata(donePayload.flow_metadata),
            completed: Boolean(donePayload.completed),
          },
        },
      };
    }
    if (streamedReply.trim()) {
      return {
        kind: "reply",
        value: {
          reply: streamedReply.trim(),
          state: {
            conversationId,
            flowMetadata: null,
            completed: false,
          },
        },
      };
    }
    return { kind: "fallback" };
  };

  let conversationId: string | undefined = input.conversationId;

  try {
    options?.onPartial?.("");

    for (let attempt = 0; attempt < 2; attempt++) {
      if (!conversationId) {
        conversationId = await startConversation();
      }
      if (!conversationId) {
        return null;
      }

      const streamAbort = new AbortController();
      const streamTimer = setTimeout(() => streamAbort.abort(), streamTimeoutMs);
      let streamAttempt: StreamAttempt;
      try {
        streamAttempt = await tryStreamingTurn(conversationId, streamAbort);
      } finally {
        clearTimeout(streamTimer);
      }

      if (streamAttempt.kind === "reply") {
        return streamAttempt.value;
      }
      if (streamAttempt.kind === "stale") {
        conversationId = undefined;
        continue;
      }

      const chatResponse = await fetch(`${apiBaseUrl()}/api/v1/chat/message`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: contentWithAttachment,
          conversation_id: conversationId || null,
        }),
      });

      if (chatResponse.status === 404) {
        conversationId = undefined;
        continue;
      }

      if (chatResponse.ok) {
        const chatData = (await chatResponse.json()) as BackendUnifiedChatResponse;
        const cid = chatData.conversation_id || conversationId || input.conversationId || "";
        return mapUnifiedToBridge(chatData, String(cid));
      }

      return null;
    }

    return null;
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      return {
        reply:
          "That took longer than expected and timed out. Please try sending your message again — your chat is still active.",
        state: { conversationId },
      };
    }
    return null;
  }
}

export async function submitChatCsat(
  input: {
    rating: number;
    conversationId?: string;
    intent?: string;
    sentiment?: string;
    comment?: string;
  },
  session: AuthSession | null,
): Promise<boolean> {
  const token = await getTokenForSession(session);
  if (!token) {
    return false;
  }
  const response = await fetch(`${apiBaseUrl()}/api/v1/feedback/csat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      rating: input.rating,
      conversation_id: input.conversationId || null,
      intent: input.intent || null,
      sentiment: input.sentiment || null,
      comment: input.comment || null,
      source: "chat",
    }),
  });
  return response.ok;
}

export async function createChatTicket(
  payload: { query: string; category: string; priority?: "low" | "medium" | "high" | "critical" },
  session: AuthSession | null,
): Promise<string | null> {
  const token = await getTokenForSession(session);
  if (!token) {
    return null;
  }
  const response = await fetch(`${apiBaseUrl()}/api/v1/tickets`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) {
    return null;
  }

  upsertLocalTicket({
    id: data.id,
    query: payload.query,
    category: payload.category,
    priority: payload.priority,
    raisedBy: getReporterEmployeeId(session),
  });
  return data.id;
}

export async function fetchPolicyAnswer(topic: string, session: AuthSession | null): Promise<string> {
  const token = await getTokenForSession(session);
  if (!token) {
    return "Looks like I can’t pull the docs right now. Generally, paid leave needs manager approval. Want me to connect you to HR?";
  }

  const query = `What is our company policy regarding: ${topic}? Answer clearly for an employee.`;
  const response = await fetch(
    `${apiBaseUrl()}/api/v1/rag/search-with-answer?${new URLSearchParams({ query })}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!response.ok) {
    return `Looks like I can’t pull policy docs right now. For "${topic}", I can share the general rule and connect you to HR for official wording.`;
  }

  const data = (await response.json()) as { answer?: string };
  return (
    data.answer?.trim() ||
    `I can’t find exact policy text for "${topic}" right now, but I can still guide you and loop in HR for confirmation.`
  );
}

export async function fetchMemoryCards(session: AuthSession | null, limit = 3): Promise<MemoryCardResponse[]> {
  const token = await getTokenForSession(session);
  if (!token) {
    return [];
  }
  const response = await fetch(`${apiBaseUrl()}/api/v1/chat/memory-cards?limit=${Math.max(1, Math.min(limit, 6))}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    return [];
  }
  return ((await response.json()) as MemoryCardResponse[]) || [];
}
