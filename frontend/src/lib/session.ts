export type UserRole = 'employee' | 'hr' | 'admin' | 'manager';

export interface AppSession {
  id?: string;
  email: string;
  name: string;
  role: UserRole;
  loginAtMs?: number;
  breakReminderAtMs?: number;
  breakReminderShownAtMs?: number;
  secondBreakReminderAtMs?: number;
  secondBreakReminderShownAtMs?: number;
  loginGreetingShownAtMs?: number;
}

const SESSION_KEY = 'mark-auth-session';

export function readSession(): AppSession | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AppSession;
  } catch {
    return null;
  }
}

export function writeSession(session: AppSession): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function patchSession(patch: Partial<AppSession>): AppSession | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const current = readSession();
  if (!current) {
    return null;
  }

  const updated: AppSession = {
    ...current,
    ...patch,
  };
  writeSession(updated);
  return updated;
}

export function clearSession(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(SESSION_KEY);
  window.localStorage.removeItem('auth_token');
}

export function inferRoleFromEmail(email: string): UserRole {
  return email.toLowerCase().includes('hr') ? 'hr' : 'employee';
}