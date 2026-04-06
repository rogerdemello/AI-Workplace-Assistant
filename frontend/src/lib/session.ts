export type UserRole = 'employee' | 'hr' | 'admin';

export interface AppSession {
  id?: string;
  email: string;
  name: string;
  role: UserRole;
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