import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight, KeyRound } from "lucide-react";
import { getDefaultRouteForRole, useAuth } from "@/contexts/AuthContext";
import { apiBaseUrl } from "@/lib/api/client";

interface SsoProvider {
  id: string;
  name: string;
}

export default function Login() {
  const nav = useNavigate();
  const location = useLocation();
  const { loginWithEmail, loginWithToken } = useAuth();
  const [email, setEmail] = useState("emp1@mark.ai");
  const [password, setPassword] = useState("password123");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ssoProviders, setSsoProviders] = useState<SsoProvider[]>([]);

  const redirectPath = (location.state as { from?: string } | null)?.from;

  // Complete an SSO round-trip: the backend redirects back here with ?sso_token=…
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ssoToken = params.get("sso_token");
    if (!ssoToken) return;
    setBusy(true);
    void loginWithToken(ssoToken)
      .then((session) => {
        // Strip the token from the URL regardless of outcome.
        window.history.replaceState({}, "", window.location.pathname);
        if (session) {
          nav(redirectPath || getDefaultRouteForRole(session.role), { replace: true });
        } else {
          setLoginError("Single sign-on failed. Please try again or use email.");
        }
      })
      .finally(() => setBusy(false));
  }, [loginWithToken, nav, redirectPath]);

  // Probe for configured SSO providers (button is hidden when none).
  useEffect(() => {
    let active = true;
    fetch(`${apiBaseUrl()}/api/v1/sso/providers`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { providers?: SsoProvider[]; enabled?: boolean } | null) => {
        if (active && data?.enabled && Array.isArray(data.providers)) {
          setSsoProviders(data.providers);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      const session = await loginWithEmail(email, password);
      if (!session) {
        setLoginError("Invalid email or password. Seed users: emp1@mark.ai and hr1@mark.ai (password123).");
        return;
      }

      setLoginError(null);
      const defaultRoute = getDefaultRouteForRole(session.role);
      nav(redirectPath || defaultRoute, { replace: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex flex-1 bg-ink text-primary-foreground p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-aurora opacity-70" />
        <div className="absolute -top-40 -left-40 size-[500px] rounded-full bg-accent/20 blur-3xl" />
        <div className="relative flex flex-col justify-between">
          <Link to="/" className="flex items-center gap-2 w-fit">
            <div className="size-8 rounded-xl bg-teal-grad grid place-items-center"><span className="font-display text-lg leading-none">M</span></div>
            <span className="font-medium">MARK</span>
          </Link>
          <div className="max-w-md">
            <h2 className="font-display text-4xl leading-tight mb-4">"I told MARK I was burning out. By 5 PM, my manager had cleared my week."</h2>
            <div className="text-sm text-primary-foreground/60">— Engineer, Series B startup</div>
          </div>
          <div className="text-xs text-primary-foreground/40">SOC2 · GDPR · ISO 27001</div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="size-8 rounded-xl bg-teal-grad grid place-items-center"><span className="font-display text-primary-foreground text-lg leading-none">M</span></div>
            <span className="font-medium">MARK</span>
          </div>

          <h1 className="font-display text-3xl tracking-tight">Welcome back</h1>
          <p className="text-sm text-muted-foreground mt-2">Sign in to continue your conversation.</p>

          <form className="mt-10 space-y-4" onSubmit={handleLogin}>
            <div>
              <label className="text-xs text-muted-foreground">Work email</label>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1 w-full h-11 px-3 rounded-lg bg-secondary border border-border focus:border-accent outline-none text-sm transition-colors"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Password</label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full h-11 px-3 rounded-lg bg-secondary border border-border focus:border-accent outline-none text-sm transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full h-11 rounded-lg bg-ink text-primary-foreground text-sm font-medium flex items-center justify-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              {busy ? "Signing in…" : "Continue"} <ArrowRight className="size-4" />
            </button>
            {loginError ? <p className="text-xs text-danger">{loginError}</p> : null}
            <p className="text-xs text-muted-foreground">Seed users: emp1@mark.ai, hr1@mark.ai — run backend `python -m scripts.seed_dummy_users`.</p>
          </form>

          <div className="mt-6 flex items-center gap-3">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const session = await loginWithEmail("emp1@mark.ai", "password123");
                  if (session) nav(getDefaultRouteForRole(session.role), { replace: true });
                } finally {
                  setBusy(false);
                }
              }}
              className="h-11 rounded-lg bg-card border border-border text-sm flex items-center justify-center gap-2 hover:border-foreground/30 transition-colors disabled:opacity-60"
            >
              <Sparkles className="size-4 text-accent" /> Employee (emp1)
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const session = await loginWithEmail("hr1@mark.ai", "password123");
                  if (session) nav(getDefaultRouteForRole(session.role), { replace: true });
                } finally {
                  setBusy(false);
                }
              }}
              className="h-11 rounded-lg bg-card border border-border text-sm flex items-center justify-center gap-2 hover:border-foreground/30 transition-colors disabled:opacity-60"
            >
              <Sparkles className="size-4 text-accent" /> HR (hr1)
            </button>
          </div>

          {ssoProviders.length > 0 && (
            <div className="mt-3 space-y-2">
              {ssoProviders.map((provider) => (
                <a
                  key={provider.id}
                  href={`${apiBaseUrl()}/api/v1/sso/${provider.id}/login`}
                  className="h-11 rounded-lg bg-card border border-border text-sm flex items-center justify-center gap-2 hover:border-foreground/30 transition-colors"
                >
                  <KeyRound className="size-4 text-accent" /> Continue with {provider.name}
                </a>
              ))}
            </div>
          )}

          <p className="mt-8 text-xs text-muted-foreground text-center">
            By continuing you agree to MARK's <a href="#" className="underline">terms</a> and <a href="#" className="underline">privacy policy</a>.
          </p>
        </div>
      </div>
    </div>
  );
}
