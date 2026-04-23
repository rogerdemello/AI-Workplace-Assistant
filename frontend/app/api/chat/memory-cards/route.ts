import { NextRequest, NextResponse } from 'next/server';

interface MemoryCardsBridgeRequest {
  limit?: number;
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

async function getChatJwt(payload: MemoryCardsBridgeRequest): Promise<string | null> {
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
  let payload: MemoryCardsBridgeRequest;

  try {
    payload = (await request.json()) as MemoryCardsBridgeRequest;
  } catch {
    payload = {};
  }

  const limit = Math.min(6, Math.max(1, Math.floor(Number(payload.limit) || 3)));
  const base = apiBaseUrl();
  const token = await getChatJwt(payload);
  if (!token) {
    return NextResponse.json({ cards: [] });
  }

  try {
    const upstream = await fetch(`${base}/api/v1/chat/memory-cards?limit=${limit}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    });

    if (!upstream.ok) {
      return NextResponse.json({ cards: [] });
    }

    const cards = (await upstream.json()) as unknown;
    return NextResponse.json({ cards });
  } catch {
    return NextResponse.json({ cards: [] });
  }
}
