import { ensureSessionToken } from "@/lib/chat-api";
import { apiBaseUrl, getJson, readStoredSession } from "@/lib/api/client";

export type CalendarProvider = "google" | "microsoft";

export interface CalendarStatus {
  connected: boolean;
  provider: CalendarProvider;
  has_refresh_token: boolean;
  expires_at: string | null;
  connected_at: string | null;
}

export interface OAuthInitResponse {
  auth_url: string;
  state: string;
  provider: CalendarProvider;
}

export async function getCalendarStatus(
  provider: CalendarProvider,
): Promise<CalendarStatus | null> {
  return getJson<CalendarStatus>(`/api/v1/integrations/calendar/${provider}/status`);
}

export async function getCalendarAuthUrl(
  provider: CalendarProvider,
  redirectUri: string,
): Promise<OAuthInitResponse | null> {
  const params = new URLSearchParams({ redirect_uri: redirectUri });
  return getJson<OAuthInitResponse>(
    `/api/v1/integrations/calendar/${provider}/auth?${params.toString()}`,
  );
}

export async function completeCalendarOAuth(
  provider: CalendarProvider,
  code: string,
  state: string,
  redirectUri: string,
): Promise<{ status: string; provider: CalendarProvider } | null> {
  const token = await ensureSessionToken(readStoredSession());
  if (!token) return null;
  try {
    const response = await fetch(
      `${apiBaseUrl()}/api/v1/integrations/calendar/${provider}/callback`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code, state, redirect_uri: redirectUri }),
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as { status: string; provider: CalendarProvider };
  } catch {
    return null;
  }
}

export function buildOAuthRedirectUri(provider: CalendarProvider): string {
  // The redirect URI is whichever route the frontend exposes to receive
  // ?code=... back from the provider. Keep this single source of truth so
  // backend + frontend agree on the value used during the OAuth handshake.
  if (typeof window === "undefined") return "";
  return `${window.location.origin}/oauth/callback/${provider}`;
}
