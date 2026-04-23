import { NextRequest, NextResponse } from 'next/server';

function apiBaseUrl(): string {
  return (
    process.env.BACKEND_API_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

interface PolicyRequest {
  topic: string;
  userEmail?: string;
  userName?: string;
  authToken?: string;
}

interface BackendStartResponse {
  conversation_id: string;
}

interface BackendChatResponse {
  response?: string;
}

async function getJwt(payload: PolicyRequest): Promise<string | null> {
  const trimmed = payload.authToken?.trim();
  if (trimmed) return trimmed;
  const base = apiBaseUrl();
  const email = (payload.userEmail || 'demo@example.com').trim() || 'demo@example.com';
  const name = (payload.userName || 'User').trim() || 'User';
  try {
    const res = await fetch(`${base}/api/v1/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name }),
      cache: 'no-store',
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token?: string };
    return data.access_token ?? null;
  } catch {
    return null;
  }
}

async function fallbackPolicyViaChat(topic: string, token: string): Promise<string | null> {
  const base = apiBaseUrl();
  try {
    const startRes = await fetch(`${base}/api/v1/chat/conversations/start`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });
    if (!startRes.ok) return null;
    const startData = (await startRes.json()) as BackendStartResponse;
    if (!startData.conversation_id) return null;

    const prompt = [
      `Policy knowledge base retrieval is currently unavailable.`,
      `Provide concise workplace guidance for "${topic}" in 2-4 lines.`,
      `Clearly mention this is general guidance and ask the employee to confirm with HR for official policy wording.`,
    ].join(' ');

    const chatRes = await fetch(`${base}/api/v1/chat/conversations/${startData.conversation_id}/respond`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: prompt }),
      cache: 'no-store',
    });
    if (!chatRes.ok) return null;
    const chatData = (await chatRes.json()) as BackendChatResponse;
    return chatData.response?.trim() || null;
  } catch {
    return null;
  }
}

/**
 * RAG-first policy answers: proxies to FastAPI `/rag/search-with-answer`.
 */
export async function POST(request: NextRequest) {
  let payload: PolicyRequest;
  try {
    payload = (await request.json()) as PolicyRequest;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }
  const topic = payload.topic?.trim();
  if (!topic) {
    return NextResponse.json({ error: 'topic is required' }, { status: 400 });
  }

  const token = await getJwt(payload);
  if (!token) {
    return NextResponse.json({ error: 'Unable to authenticate policy request' }, { status: 502 });
  }

  const query = `What is our company policy regarding: ${topic}? Answer clearly for an employee. If documents do not contain the answer, say so.`;
  const base = apiBaseUrl();
  const url = `${base}/api/v1/rag/search-with-answer?${new URLSearchParams({ query })}`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (!res.ok) {
    const detail = await res.text();
    const fallbackAnswer = await fallbackPolicyViaChat(topic, token);
    if (fallbackAnswer) {
      return NextResponse.json({
        answer: fallbackAnswer,
        citations: [],
        source: 'chat_fallback',
      });
    }
    return NextResponse.json(
      { error: 'RAG request failed', detail: detail.slice(0, 400), upstreamStatus: res.status },
      { status: 502 }
    );
  }

  const data = (await res.json()) as { answer?: string; citations?: unknown[] };
  const answer = typeof data.answer === 'string' ? data.answer : '';
  if (!answer.trim()) {
    const fallbackAnswer = await fallbackPolicyViaChat(topic, token);
    if (fallbackAnswer) {
      return NextResponse.json({
        answer: fallbackAnswer,
        citations: [],
        source: 'chat_fallback',
      });
    }
    return NextResponse.json({
      answer:
        'I could not find a matching policy passage in the uploaded documents yet. Please contact HR or upload the relevant handbook section.',
      source: 'fallback',
    });
  }

  return NextResponse.json({ answer, citations: data.citations ?? [], source: 'rag' });
}
