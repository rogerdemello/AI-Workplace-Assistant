import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { apiBaseUrl, readStoredSession } from "@/lib/api/client";
import { ensureSessionToken } from "@/lib/chat-api";

type Period = "weekly" | "monthly";

export function DownloadReportButton() {
  const [busy, setBusy] = useState<Period | null>(null);

  async function download(period: Period) {
    setBusy(period);
    try {
      const token = await ensureSessionToken(readStoredSession());
      if (!token) return;
      const res = await fetch(
        `${apiBaseUrl()}/api/v1/analytics/report?period=${period}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) return;
      const blob = await res.blob();
      const filename =
        res.headers.get("content-disposition")?.match(/filename="?([^"]+)"?/)?.[1] ??
        `mark-hr-${period}.csv`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => download("weekly")}
        disabled={busy !== null}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-sm hover:bg-secondary/50 disabled:opacity-60"
      >
        {busy === "weekly" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Download className="size-3.5" />
        )}
        Weekly report
      </button>
      <button
        type="button"
        onClick={() => download("monthly")}
        disabled={busy !== null}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-sm hover:bg-secondary/50 disabled:opacity-60"
      >
        {busy === "monthly" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Download className="size-3.5" />
        )}
        Monthly report
      </button>
    </div>
  );
}
