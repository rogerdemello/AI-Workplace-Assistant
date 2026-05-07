/**
 * Next.js API routes proxy to FastAPI using the browser JWT only (no demo-login fallback).
 */
export function jwtFromClientPayload(authToken?: string): string | null {
  const t = authToken?.trim();
  return t || null;
}
