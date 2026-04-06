import { readSession } from '@/lib/session';

const apiBase = (): string =>
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000';

/**
 * Exchange the same credentials used for Supabase login for a FastAPI JWT.
 * Seed users (e.g. hr@mark.ai / password123) exist in both systems after `seed_dummy_users`.
 */
export async function syncBackendAuthTokenWithPassword(email: string, password: string): Promise<boolean> {
  if (typeof window === 'undefined') {
    return false;
  }
  const base = apiBase().replace(/\/$/, '');
  try {
    const res = await fetch(`${base}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      return false;
    }
    const data = (await res.json()) as { access_token?: string };
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * When the UI session exists but `auth_token` is missing (new tab, cleared storage),
 * obtain a JWT via demo login. Works for seeded users (role comes from DB).
 */
export async function ensureBackendAuthToken(): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }
  if (localStorage.getItem('auth_token')) {
    return;
  }
  const session = readSession();
  if (!session?.email) {
    return;
  }
  const base = apiBase().replace(/\/$/, '');
  try {
    const res = await fetch(`${base}/api/v1/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: session.email, name: session.name || 'User' }),
    });
    if (!res.ok) {
      return;
    }
    const data = (await res.json()) as { access_token?: string };
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }
  } catch {
    // Dashboard will fall back to Supabase/mock ticket sources
  }
}
