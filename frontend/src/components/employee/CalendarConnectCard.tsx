import { useCallback, useEffect, useState } from "react";
import { Calendar } from "lucide-react";
import { toast } from "sonner";
import {
  buildOAuthRedirectUri,
  getCalendarAuthUrl,
  getCalendarStatus,
  type CalendarProvider,
  type CalendarStatus,
} from "@/lib/api/calendar";
import { cn } from "@/lib/utils";

const PROVIDERS: { key: CalendarProvider; label: string; tone: string }[] = [
  { key: "google", label: "Google Calendar", tone: "bg-card hover:bg-secondary" },
  { key: "microsoft", label: "Outlook / Microsoft 365", tone: "bg-card hover:bg-secondary" },
];

export function CalendarConnectCard() {
  const [statuses, setStatuses] = useState<Record<CalendarProvider, CalendarStatus | null>>({
    google: null,
    microsoft: null,
  });
  const [busy, setBusy] = useState<CalendarProvider | null>(null);

  const refresh = useCallback(async () => {
    const [g, m] = await Promise.all([
      getCalendarStatus("google"),
      getCalendarStatus("microsoft"),
    ]);
    setStatuses({ google: g, microsoft: m });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const connect = async (provider: CalendarProvider) => {
    setBusy(provider);
    try {
      const redirect = buildOAuthRedirectUri(provider);
      const result = await getCalendarAuthUrl(provider, redirect);
      if (!result?.auth_url) {
        toast.error("Could not start OAuth. Is the provider configured on the server?");
        return;
      }
      // Open in same tab so the OAuth handshake returns to /oauth/callback
      // with code + state in the URL.
      window.location.href = result.auth_url;
    } finally {
      setBusy(null);
    }
  };

  const anyConnected = statuses.google?.connected || statuses.microsoft?.connected;

  return (
    <div className="mt-10 rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="size-4 text-muted-foreground" />
        <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Calendar</div>
      </div>
      <p className="text-sm text-muted-foreground">
        {anyConnected
          ? "MARK can read your free/busy and propose meeting times."
          : "Connect your calendar so MARK can suggest meeting times that fit your schedule."}
      </p>
      <div className="mt-4 grid sm:grid-cols-2 gap-3">
        {PROVIDERS.map((p) => {
          const status = statuses[p.key];
          const isConnected = status?.connected ?? false;
          return (
            <div
              key={p.key}
              className="rounded-xl border border-border p-4 flex flex-col gap-3 justify-between"
            >
              <div>
                <div className="text-sm font-medium">{p.label}</div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  {isConnected
                    ? status?.connected_at
                      ? `Connected ${new Date(status.connected_at).toLocaleDateString()}`
                      : "Connected"
                    : "Not connected"}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void connect(p.key)}
                disabled={busy !== null}
                className={cn(
                  "text-xs px-3 py-1.5 rounded-md border border-border transition-colors disabled:opacity-50",
                  isConnected ? "bg-emerald-soft text-emerald border-emerald/30" : p.tone,
                )}
              >
                {busy === p.key
                  ? "Opening provider…"
                  : isConnected
                    ? "Reconnect"
                    : "Connect"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
