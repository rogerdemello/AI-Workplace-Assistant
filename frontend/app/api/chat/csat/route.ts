import { NextRequest, NextResponse } from 'next/server';

interface CsatBridgeRequest {
  rating: number;
  conversationId?: string;
  comment?: string;
  intent?: string;
  sentiment?: string;
  source?: string;
  userEmail?: string;
  userName?: string;
  authToken?: string;
}

function apiBaseUrl(): string {
  return (
    process.env.BACKEND_API_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

async function getChatJwt(payload: CsatBridgeRequest): Promise<string | null> {
  const base = apiBaseUrl();
  const email = (payload.userEmail || 'demo@example.com').trim() || 'demo@example.com';
  const name = (payload.userName || 'Demo User').trim() || 'Demo User';

  const trimmed = payload.authToken?.trim();
  if (trimmed) {
    return trimmed;
  }

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

export async function POST(request: NextRequest) {
  let payload: CsatBridgeRequest;

  try {
    payload = (await request.json()) as CsatBridgeRequest;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON payload' }, { status: 400 });
  }

  const rating = Number(payload.rating);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    return NextResponse.json({ error: 'rating must be an integer between 1 and 5' }, { status: 400 });
  }

  const base = apiBaseUrl();
  const token = await getChatJwt(payload);
  if (!token) {
    return NextResponse.json({ error: 'Unable to authenticate CSAT request' }, { status: 502 });
  }

  const upstream = await fetch(`${base}/api/v1/feedback/csat`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      rating,
      conversation_id: payload.conversationId || null,
      comment: payload.comment || null,
      intent: payload.intent || null,
      sentiment: payload.sentiment || null,
      source: payload.source || 'chat',
    }),
    cache: 'no-store',
  });

  if (!upstream.ok) {
    const detail = await upstream.text();
    return NextResponse.json(
      { error: 'Failed to submit CSAT', upstreamStatus: upstream.status, detail: detail.slice(0, 400) },
      { status: 502 }
    );
  }

  return NextResponse.json(await upstream.json());
}
