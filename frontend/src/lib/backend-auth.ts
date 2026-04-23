import { readSession } from '@/lib/session';

const apiBase = (): string =>
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000';

async function loginDemoForSession(email: string, name: string): Promise<string | null> {
  const base = apiBase().replace(/\/$/, '');
  try {
    const res = await fetch(`${base}/api/v1/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name }),
    });
    if (!res.ok) {
      return null;
    }
    const data = (await res.json()) as { access_token?: string };
    return data.access_token ?? null;
  } catch {
    return null;
  }
}

/**
 * Exchange the same credentials used for Supabase login for a FastAPI JWT.
 * Seed users (e.g. hr@mark.ai / password123) exist in both systems after `seed_dummy_users`.
 */
export async function syncBackendAuthTokenWithPassword(email: string, password: string): Promise<boolean> {
  if (typeof window === 'undefined') {
    return false;
  }
  const base = apiBase().replace(/\/$/, '');

  // Avoid reusing stale tokens when credentials changed or backend auth failed.
  localStorage.removeItem('auth_token');

  try {
    const res = await fetch(`${base}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) {
      const data = (await res.json()) as { access_token?: string };
      if (data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
        return true;
      }
    }

    // Fallback: for local/dev flows where backend user/password is not seeded,
    // still obtain a valid JWT tied to the signed-in UI identity.
    const demoToken = await loginDemoForSession(email, readSession()?.name || 'User');
    if (demoToken) {
      localStorage.setItem('auth_token', demoToken);
      return true;
    }
    return false;
  } catch {
    const demoToken = await loginDemoForSession(email, readSession()?.name || 'User');
    if (demoToken) {
      localStorage.setItem('auth_token', demoToken);
      return true;
    }
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

  const session = readSession();
  if (!session?.email) {
    return;
  }

  const existing = localStorage.getItem('auth_token');
  const base = apiBase().replace(/\/$/, '');

  try {
    if (existing) {
      const meRes = await fetch(`${base}/api/v1/auth/me`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${existing}` },
      });
      if (meRes.ok) {
        return;
      }
      localStorage.removeItem('auth_token');
    }

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
