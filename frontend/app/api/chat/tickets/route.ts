import { NextRequest, NextResponse } from 'next/server';
import { jwtFromClientPayload } from '@/lib/server-chat-jwt';

interface CreateTicketRequest {
  query: string;
  category: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  /** Match logged-in user so the ticket is stored under their FastAPI user (visible to HR). */
  userEmail?: string;
  userName?: string;
  /** JWT from the browser after login (`syncBackendAuthTokenWithPassword`). */
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
  const token = jwtFromClientPayload(payload.authToken);
  if (!token) {
    return NextResponse.json(
      {
        error: 'Unable to authenticate ticket request',
        hint:
          'Sign in via the app login so `auth_token` is stored, or pass `authToken` in the request body. Start the backend and set BACKEND_API_URL / NEXT_PUBLIC_API_URL if needed.',
        backendBase: base,
      },
      { status: 502 }
    );
  }

  const response = await postTicket(base, token, payload);

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
