import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bell, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { getJson } from "@/lib/api/client";

interface AlertRow {
  id: string;
  title: string;
  body: string | null;
  severity: string;
  alert_type: string | null;
  source: string;
  created_at: string;
  acknowledged: boolean;
}

type SeverityKey = "critical" | "high" | "medium" | "low";

const SEVERITY_ORDER: SeverityKey[] = ["critical", "high", "medium", "low"];

const SEVERITY_STYLE: Record<SeverityKey, { label: string; tone: string; icon: typeof Bell }> = {
  critical: { label: "Critical", tone: "border-danger/40 bg-danger-soft/30 text-danger", icon: ShieldAlert },
  high: { label: "High", tone: "border-danger/30 bg-danger-soft/15 text-danger", icon: AlertTriangle },
  medium: { label: "Medium", tone: "border-warning/30 bg-warning-soft/30 text-warning", icon: Bell },
  low: { label: "Low", tone: "border-border bg-card text-muted-foreground", icon: Bell },
};

function normaliseSeverity(s: string): SeverityKey {
  const lower = (s || "").toLowerCase();
  if (lower === "critical" || lower === "high" || lower === "medium" || lower === "low") {
    return lower;
  }
  return "medium";
}

export function AlertsPanelCard({ limit = 30 }: { limit?: number }) {
  const [rows, setRows] = useState<AlertRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getJson<AlertRow[]>(`/api/v1/alerts?limit=${limit}`).then((data) => {
      if (cancelled) return;
      setRows(Array.isArray(data) ? data : []);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [limit]);

  const grouped = useMemo(() => {
    const out: Record<SeverityKey, AlertRow[]> = { critical: [], high: [], medium: [], low: [] };
    for (const r of rows.filter((r) => !r.acknowledged)) {
      out[normaliseSeverity(r.severity)].push(r);
    }
    return out;
  }, [rows]);

  const totalOpen = SEVERITY_ORDER.reduce((sum, k) => sum + grouped[k].length, 0);

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">HR alerts</div>
          <div className="text-sm font-medium mt-0.5">
            {loading ? "Loading…" : `${totalOpen} unacknowledged`}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
      ) : totalOpen === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No active alerts. Good news.
        </div>
      ) : (
        <div className="space-y-4">
          {SEVERITY_ORDER.map((sev) => {
            const items = grouped[sev];
            if (items.length === 0) return null;
            const style = SEVERITY_STYLE[sev];
            const Icon = style.icon;
            return (
              <div key={sev}>
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border",
                      style.tone,
                    )}
                  >
                    <Icon className="size-3" /> {style.label}
                  </span>
                  <span className="text-[11px] text-muted-foreground">{items.length}</span>
                </div>
                <ul className="space-y-2">
                  {items.slice(0, 5).map((a) => (
                    <li
                      key={a.id}
                      className="rounded-lg border border-border/70 bg-secondary/30 p-3 text-sm"
                    >
                      <div className="font-medium leading-tight">{a.title}</div>
                      {a.alert_type && (
                        <div className="text-[11px] text-muted-foreground mt-0.5">{a.alert_type}</div>
                      )}
                      <div className="text-[11px] text-muted-foreground mt-1">
                        {new Date(a.created_at).toLocaleString()}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
