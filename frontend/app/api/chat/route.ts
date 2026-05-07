import { NextRequest, NextResponse } from 'next/server';
import { jwtFromClientPayload } from '@/lib/server-chat-jwt';

interface ChatBridgeRequest {
  message: string;
  state?: {
    conversationId?: string;
    intent?: string;
    step?: string;
  };
  userEmail?: string;
  userName?: string;
  authToken?: string;
}

async function parsePayload(request: NextRequest): Promise<ChatBridgeRequest | null> {
  const contentType = request.headers.get('content-type') || '';

  if (contentType.includes('multipart/form-data')) {
    const form = await request.formData();
    const stateRaw = String(form.get('state') || '');
    let state: ChatBridgeRequest['state'] | undefined;
    if (stateRaw) {
      try {
        state = JSON.parse(stateRaw) as ChatBridgeRequest['state'];
      } catch {
        state = undefined;
      }
    }

    return {
      message: String(form.get('message') || ''),
      state,
      userEmail: String(form.get('userEmail') || ''),
      userName: String(form.get('userName') || ''),
      authToken: String(form.get('authToken') || ''),
    };
  }

  try {
    return (await request.json()) as ChatBridgeRequest;
  } catch {
    return null;
  }
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

function apiBaseUrl(): string {
  return (
    process.env.BACKEND_API_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

function getChatJwt(payload: ChatBridgeRequest): string | null {
  return jwtFromClientPayload(payload.authToken);
}

export async function POST(request: NextRequest) {
  const payload = await parsePayload(request);
  if (!payload) {
    return NextResponse.json({ error: 'Invalid JSON payload' }, { status: 400 });
  }

  const message = payload.message?.trim();
  if (!message) {
    return NextResponse.json({ error: 'message is required' }, { status: 400 });
  }

  const base = apiBaseUrl();
  const token = getChatJwt(payload);
  if (!token) {
    return NextResponse.json(
      {
        error: 'Unable to authenticate chat request',
        hint: 'Sign in via the app login so `auth_token` is stored, or pass `authToken` in the chat request body.',
        backendBase: base,
      },
      { status: 502 }
    );
  }

  let conversationId = payload.state?.conversationId;
  const authHeaders = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  if (!conversationId) {
    const startResponse = await fetch(`${base}/api/v1/chat/conversations/start`, {
      method: 'POST',
      headers: authHeaders,
      cache: 'no-store',
    });

    if (!startResponse.ok) {
      const detail = await startResponse.text();
      return NextResponse.json(
        { error: 'Failed to start chat conversation', upstreamStatus: startResponse.status, detail: detail.slice(0, 400) },
        { status: 502 }
      );
    }

    const startData = (await startResponse.json()) as BackendStartResponse;
    conversationId = startData.conversation_id;
  }

  const chatResponse = await fetch(`${base}/api/v1/chat/conversations/${conversationId}/respond`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ message }),
    cache: 'no-store',
  });

  if (!chatResponse.ok) {
    const detail = await chatResponse.text();
    return NextResponse.json(
      { error: 'Failed to get chat response', upstreamStatus: chatResponse.status, detail: detail.slice(0, 400) },
      { status: 502 }
    );
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
