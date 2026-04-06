import { NextRequest, NextResponse } from 'next/server';

interface CreateTicketRequest {
  query: string;
  category: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  /** Match logged-in user so the ticket is stored under their FastAPI user (visible to HR). */
  userEmail?: string;
  userName?: string;
  /** JWT from the browser after login (`syncBackendAuthTokenWithPassword`); avoids demo/login when backend is up. */
  authToken?: string;
}

/** Server-side route must reach FastAPI; use BACKEND_API_URL if NEXT_PUBLIC_* is wrong for Node (Docker, etc.). */
function apiBaseUrl(): string {
  return (
    process.env.BACKEND_API_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

async function getChatToken(userEmail?: string, userName?: string): Promise<string | null> {
  const base = apiBaseUrl();
  const email = (userEmail || 'demo@example.com').trim() || 'demo@example.com';
  const name = (userName || 'Demo User').trim() || 'Demo User';
  try {
    const loginResponse = await fetch(`${base}/api/v1/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email }),
      cache: 'no-store',
    });

    if (!loginResponse.ok) {
      return null;
    }

    const loginData = (await loginResponse.json()) as { access_token?: string };
    return loginData.access_token ?? null;
  } catch {
    return null;
  }
}

async function postTicket(base: string, token: string, payload: CreateTicketRequest): Promise<Response> {
  return fetch(`${base}/api/v1/tickets`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: payload.query.trim(),
      category: payload.category.trim(),
      priority: payload.priority ?? 'medium',
    }),
    cache: 'no-store',
  });
}

export async function POST(request: NextRequest) {
  let payload: CreateTicketRequest;

  try {
    payload = (await request.json()) as CreateTicketRequest;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON payload' }, { status: 400 });
  }

  if (!payload.query?.trim() || !payload.category?.trim()) {
    return NextResponse.json({ error: 'query and category are required' }, { status: 400 });
  }

  const base = apiBaseUrl();
  let token = payload.authToken?.trim() || null;
  if (!token) {
    token = await getChatToken(payload.userEmail, payload.userName);
  }
  if (!token) {
    return NextResponse.json(
      {
        error: 'Unable to authenticate ticket request',
        hint:
          'FastAPI is unreachable or demo login failed. Start the backend (e.g. uvicorn on port 8000). If it runs elsewhere, set BACKEND_API_URL or NEXT_PUBLIC_API_URL to the full base URL (no trailing slash).',
        backendBase: base,
      },
      { status: 502 }
    );
  }

  let response = await postTicket(base, token, payload);

  if (response.status === 401 && payload.authToken) {
    const fallback = await getChatToken(payload.userEmail, payload.userName);
    if (fallback) {
      response = await postTicket(base, fallback, payload);
    }
  }

  if (!response.ok) {
    const detail = await response.text();
    return NextResponse.json(
      {
        error: 'Failed to create ticket',
        upstreamStatus: response.status,
        detail: detail.slice(0, 500),
      },
      { status: 502 }
    );
  }

  const ticket = (await response.json()) as { id?: string; status?: string; category?: string };
  return NextResponse.json({
    id: ticket.id,
    status: ticket.status,
    category: ticket.category,
  });
}
