import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { MARK_AUTH_INVALID_EVENT, verifyStoredCredentialOnce } from "@/lib/chat-api";

export type UserRole = "employee" | "hr" | "manager";

export interface AuthSession {
  email: string;
  name: string;
  role: UserRole;
  userId?: string;
  loginAtMs?: number;
  breakReminderAtMs?: number;
  secondBreakReminderAtMs?: number;
  breakReminderShownAtMs?: number;
  secondBreakReminderShownAtMs?: number;
}

interface AuthContextValue {
  session: AuthSession | null;
  /** Real API login against seeded users (see `scripts/seed_dummy_users.py`). */
  loginWithEmail: (email: string, password: string) => Promise<AuthSession | null>;
  /** Establish a session from an already-issued access token (e.g. SSO redirect). */
  loginWithToken: (accessToken: string) => Promise<AuthSession | null>;
  logout: () => void;
}

const STORAGE_KEY = "mark.auth.session";

function apiBaseUrl(): string {
  const envValue =
    (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
    (typeof import.meta !== "undefined" && import.meta.env?.NEXT_PUBLIC_API_URL);
  return String(envValue || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function mapApiRole(role: string): UserRole {
  const r = (role || "").toLowerCase();
  if (r === "hr") return "hr";
  if (r === "manager") return "manager";
  if (r === "admin") return "hr";
  return "employee";
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(STORAGE_KEY);
    if (!rawValue) {
      return null;
    }

    const parsedSession = JSON.parse(rawValue) as AuthSession;
    if (parsedSession?.email && parsedSession?.role) {
      return parsedSession;
    }
  } catch {
    // Ignore malformed local storage values and treat as logged out.
  }

  return null;
}

function readInitialSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const sess = readStoredSession();
  const token = window.localStorage.getItem("auth_token");
  if (sess && !token) {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
  return sess;
}

export function getDefaultRouteForRole(role: UserRole): string {
  if (role === "hr") return "/dashboard";
  if (role === "manager") return "/manager";
  return "/employee";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => readInitialSession());

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const syncLogout = () => {
      setSession(null);
      window.localStorage.removeItem(STORAGE_KEY);
      window.localStorage.removeItem("auth_token");
    };
    window.addEventListener(MARK_AUTH_INVALID_EVENT, syncLogout as EventListener);
    void verifyStoredCredentialOnce();
    return () => window.removeEventListener(MARK_AUTH_INVALID_EVENT, syncLogout as EventListener);
  }, []);

  const establishSessionFromToken = async (accessToken: string, fallbackEmail = ""): Promise<AuthSession | null> => {
    if (!accessToken || typeof window === "undefined") return null;
    const now = Date.now();
    try {
      window.localStorage.setItem("auth_token", accessToken);
      const meResponse = await fetch(`${apiBaseUrl()}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!meResponse.ok) {
        window.localStorage.removeItem("auth_token");
        return null;
      }
      const me = (await meResponse.json()) as { id?: string; name?: string; email?: string; role?: string };
      const email = me.email ? String(me.email).toLowerCase() : fallbackEmail;
      const nextSession: AuthSession = {
        email,
        name: me.name ? String(me.name) : email.split("@")[0],
        role: mapApiRole(String(me.role ?? "employee")),
        userId: me.id ? String(me.id) : undefined,
        loginAtMs: now,
        breakReminderAtMs: now + 2 * 60 * 60 * 1000,
        secondBreakReminderAtMs: now + Math.round(5.5 * 60 * 60 * 1000),
        breakReminderShownAtMs: 0,
        secondBreakReminderShownAtMs: 0,
      };
      setSession(nextSession);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
      return nextSession;
    } catch {
      return null;
    }
  };

  const contextValue = useMemo<AuthContextValue>(
    () => ({
      session,
      loginWithToken: (accessToken: string) => establishSessionFromToken(accessToken),
      loginWithEmail: async (emailInput: string, password: string) => {
        const email = emailInput.trim().toLowerCase();
        const pwd = password.trim();
        if (!email || !pwd) {
          return null;
        }
        const now = Date.now();

        try {
          const loginResponse = await fetch(`${apiBaseUrl()}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password: pwd }),
          });
          if (!loginResponse.ok) {
            return null;
          }
          const tokenPayload = (await loginResponse.json()) as { access_token?: string };
          if (!tokenPayload.access_token || typeof window === "undefined") {
            return null;
          }
          window.localStorage.setItem("auth_token", tokenPayload.access_token);

          const meResponse = await fetch(`${apiBaseUrl()}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${tokenPayload.access_token}` },
          });
          if (!meResponse.ok) {
            return null;
          }
          const me = (await meResponse.json()) as { id?: string; name?: string; email?: string; role?: string };
          const nextSession: AuthSession = {
            email: me.email ? String(me.email).toLowerCase() : email,
            name: me.name ? String(me.name) : email.split("@")[0],
            role: mapApiRole(String(me.role ?? "employee")),
            userId: me.id ? String(me.id) : undefined,
            loginAtMs: now,
            breakReminderAtMs: now + 2 * 60 * 60 * 1000,
            secondBreakReminderAtMs: now + Math.round(5.5 * 60 * 60 * 1000),
            breakReminderShownAtMs: 0,
            secondBreakReminderShownAtMs: 0,
          };

          setSession(nextSession);
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
          return nextSession;
        } catch {
          return null;
        }
      },
      logout: () => {
        setSession(null);
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(STORAGE_KEY);
          window.localStorage.removeItem("auth_token");
        }
      },
    }),
    [session],
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const authContext = useContext(AuthContext);
  if (!authContext) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return authContext;
}
