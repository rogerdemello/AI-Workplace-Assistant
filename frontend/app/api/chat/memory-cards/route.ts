import { NextRequest, NextResponse } from 'next/server';
import { jwtFromClientPayload } from '@/lib/server-chat-jwt';

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

function getChatJwt(payload: MemoryCardsBridgeRequest): string | null {
  return jwtFromClientPayload(payload.authToken);
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
  const token = getChatJwt(payload);
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
