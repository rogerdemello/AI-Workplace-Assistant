import { NextRequest, NextResponse } from 'next/server';

interface ChatBridgeRequest {
  message: string;
  state?: {
    conversationId?: string;
  };
}

interface BackendStartResponse {
  conversation_id: string;
  greeting?: string;
}

interface BackendChatResponse {
  response?: string;
  intent?: string;
  sentiment?: string;
  context?: Record<string, unknown>;
  conversation_state?: Record<string, unknown>;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function getDemoToken(): Promise<string | null> {
  try {
    const loginResponse = await fetch(`${API_BASE_URL}/api/v1/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Demo User', email: 'demo@example.com' }),
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
  let payload: ChatBridgeRequest;

  try {
    payload = (await request.json()) as ChatBridgeRequest;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON payload' }, { status: 400 });
  }

  const message = payload.message?.trim();
  if (!message) {
    return NextResponse.json({ error: 'message is required' }, { status: 400 });
  }

  const token = await getDemoToken();
  if (!token) {
    return NextResponse.json({ error: 'Unable to authenticate chat request' }, { status: 502 });
  }

  let conversationId = payload.state?.conversationId;
  const authHeaders = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  if (!conversationId) {
    const startResponse = await fetch(`${API_BASE_URL}/api/v1/chat/conversations/start`, {
      method: 'POST',
      headers: authHeaders,
      cache: 'no-store',
    });

    if (!startResponse.ok) {
      return NextResponse.json({ error: 'Failed to start chat conversation' }, { status: 502 });
    }

    const startData = (await startResponse.json()) as BackendStartResponse;
    conversationId = startData.conversation_id;
  }

  const chatResponse = await fetch(`${API_BASE_URL}/api/v1/chat/conversations/${conversationId}/respond`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ message }),
    cache: 'no-store',
  });

  if (!chatResponse.ok) {
    return NextResponse.json({ error: 'Failed to get chat response' }, { status: 502 });
  }

  const chatData = (await chatResponse.json()) as BackendChatResponse;

  return NextResponse.json({
    reply: chatData.response ?? 'I could not generate a response right now.',
    state: {
      conversationId,
      intent: chatData.intent,
      sentiment: chatData.sentiment,
      context: chatData.context,
      conversationState: chatData.conversation_state,
    },
  });
}
