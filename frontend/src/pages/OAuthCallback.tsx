import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import {
  buildOAuthRedirectUri,
  completeCalendarOAuth,
  type CalendarProvider,
} from "@/lib/api/calendar";

type Status = "exchanging" | "success" | "error";

const PROVIDER_LABEL: Record<string, string> = {
  google: "Google Calendar",
  microsoft: "Outlook / Microsoft 365",
};

export default function OAuthCallback() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<Status>("exchanging");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (!provider || (provider !== "google" && provider !== "microsoft")) {
      setStatus("error");
      setErrorMessage("Unknown provider.");
      return;
    }
    if (error) {
      setStatus("error");
      setErrorMessage(error);
      return;
    }
    if (!code || !state) {
      setStatus("error");
      setErrorMessage("Missing code or state in the redirect URL.");
      return;
    }

    void (async () => {
      const result = await completeCalendarOAuth(
        provider as CalendarProvider,
        code,
        state,
        buildOAuthRedirectUri(provider as CalendarProvider),
      );
      if (result?.status === "connected") {
        setStatus("success");
      } else {
        setStatus("error");
        setErrorMessage("Token exchange failed. Try connecting again.");
      }
    })();
  }, [provider, searchParams]);

  const label = PROVIDER_LABEL[provider || ""] || "calendar";

  return (
    <AppLayout title="Connecting calendar" subtitle={`OAuth handshake with ${label}`}>
      <div className="px-6 lg:px-10 py-12 max-w-xl">
        {status === "exchanging" && (
          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="text-sm font-medium">Finishing the connection…</div>
            <p className="text-xs text-muted-foreground mt-2">
              Exchanging the authorization code for tokens. This usually finishes in a second.
            </p>
          </div>
        )}
        {status === "success" && (
          <div className="rounded-2xl border border-emerald/40 bg-emerald-soft/30 p-6">
            <div className="text-sm font-medium">Connected.</div>
            <p className="text-xs text-muted-foreground mt-2">
              MARK can now read your {label} free/busy and create events on your behalf.
            </p>
            <Link to="/employee" className="text-xs text-accent underline mt-3 inline-block">
              Back to dashboard
            </Link>
          </div>
        )}
        {status === "error" && (
          <div className="rounded-2xl border border-danger/40 bg-danger-soft/20 p-6">
            <div className="text-sm font-medium">Something went wrong.</div>
            <p className="text-xs text-muted-foreground mt-2">{errorMessage}</p>
            <Link to="/employee" className="text-xs text-accent underline mt-3 inline-block">
              Back to dashboard
            </Link>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
