const apiBase = (): string =>
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000';

/**
 * Exchange email + password for a FastAPI JWT (`POST /api/v1/auth/login`).
 * Seed users: `employee1@infeedo.ai` and `hr1@infeedo.ai` (see `backend/scripts/seed_dummy_users.py`).
 */
export async function syncBackendAuthTokenWithPassword(email: string, password: string): Promise<boolean> {
  if (typeof window === 'undefined') {
    return false;
  }
  const base = apiBase().replace(/\/$/, '');

  localStorage.removeItem('auth_token');

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
 * When `auth_token` exists, keep it if `/auth/me` succeeds; otherwise clear it.
 * Does not mint a new token without the user's password — user must sign in again.
 */
export async function ensureBackendAuthToken(): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }

  const existing = localStorage.getItem('auth_token');
  if (!existing) {
    return;
  }

  const base = apiBase().replace(/\/$/, '');

  try {
    const meRes = await fetch(`${base}/api/v1/auth/me`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${existing}` },
    });
    if (!meRes.ok) {
      localStorage.removeItem('auth_token');
    }
  } catch {
    localStorage.removeItem('auth_token');
  }
}
