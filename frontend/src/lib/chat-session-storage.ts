/**
 * Persists employee chat UI state per logged-in user (email key).
 * Isolates each employee's thread from others on the same browser.
 */

import type { ChatRecord, ControlState, FlowState } from '@/types/employee-chat';

const VERSION = 1 as const;
const PREFIX = 'mark-employee-chat';

function storageKey(email: string): string {
  return `${PREFIX}:${email.trim().toLowerCase()}`;
}

export interface PersistedChatSnapshot {
  version: typeof VERSION;
  messages: ChatRecord[];
  flow: FlowState | null;
  control: ControlState;
}

export function loadChatSnapshot(email: string | undefined | null): PersistedChatSnapshot | null {
  if (typeof window === 'undefined' || !email?.trim()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(storageKey(email));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedChatSnapshot;
    if (parsed.version !== VERSION || !Array.isArray(parsed.messages)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveChatSnapshot(email: string | undefined | null, snapshot: Omit<PersistedChatSnapshot, 'version'>): void {
  if (typeof window === 'undefined' || !email?.trim()) {
    return;
  }

  try {
    const payload: PersistedChatSnapshot = { version: VERSION, ...snapshot };
    window.localStorage.setItem(storageKey(email), JSON.stringify(payload));
  } catch {
    // Quota or private mode — ignore
  }
}

export function clearChatSnapshot(email: string | undefined | null): void {
  if (typeof window === 'undefined' || !email?.trim()) {
    return;
  }
  try {
    window.localStorage.removeItem(storageKey(email));
  } catch {
    /* ignore */
  }
}
