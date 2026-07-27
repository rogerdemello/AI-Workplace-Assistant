import type { ChatRecord, FlowMetadata } from "@/types/chat";

const VERSION = 2 as const;
const PREFIX = "mark-employee-chat";

function getStorageKey(email: string): string {
  return `${PREFIX}:${email.trim().toLowerCase()}`;
}

export interface PersistedChatSnapshot {
  version: typeof VERSION;
  messages: ChatRecord[];
  conversationId?: string | null;
  flowMetadata?: FlowMetadata | null;
}

export function loadChatSnapshot(email: string | null | undefined): PersistedChatSnapshot | null {
  if (typeof window === "undefined" || !email?.trim()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(getStorageKey(email));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as PersistedChatSnapshot & { version?: number; flow?: unknown };
    if (!Array.isArray(parsed.messages)) {
      return null;
    }
    if (parsed.version !== VERSION) {
      return null;
    }
    return parsed as PersistedChatSnapshot;
  } catch {
    return null;
  }
}

/**
 * Watermark for proactive nudges already shown to this user.
 *
 * Kept under its own key rather than inside the snapshot so adding it doesn't
 * change the snapshot VERSION — a bump would discard every existing transcript.
 */
function getNudgeWatermarkKey(email: string): string {
  return `${PREFIX}:nudge-seen:${email.trim().toLowerCase()}`;
}

export function loadNudgeWatermark(email: string | null | undefined): string | null {
  if (typeof window === "undefined" || !email?.trim()) {
    return null;
  }
  try {
    return window.localStorage.getItem(getNudgeWatermarkKey(email));
  } catch {
    return null;
  }
}

export function saveNudgeWatermark(email: string | null | undefined, isoTimestamp: string): void {
  if (typeof window === "undefined" || !email?.trim() || !isoTimestamp) {
    return;
  }
  try {
    window.localStorage.setItem(getNudgeWatermarkKey(email), isoTimestamp);
  } catch {
    // Ignore storage quota/private mode errors.
  }
}

export function saveChatSnapshot(
  email: string | null | undefined,
  snapshot: Omit<PersistedChatSnapshot, "version">,
): void {
  if (typeof window === "undefined" || !email?.trim()) {
    return;
  }

  try {
    const payload: PersistedChatSnapshot = {
      version: VERSION,
      ...snapshot,
    };
    window.localStorage.setItem(getStorageKey(email), JSON.stringify(payload));
  } catch {
    // Ignore storage quota/private mode errors.
  }
}
