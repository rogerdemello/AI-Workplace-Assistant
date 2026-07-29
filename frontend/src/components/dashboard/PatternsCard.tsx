import { useEffect, useState } from "react";
import { AlertCircle, ArrowRight, ShieldAlert, TrendingDown, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { getJson } from "@/lib/api/client";

interface Pattern {
  type: "emotion_cluster" | "department_drop" | "complaint_category" | "at_risk_individual";
  label: string;
  affected_count: number;
  severity: "high" | "medium" | "low";
  recommendation: string;
}

interface PatternsResponse {
  window_days: number;
  patterns: Pattern[];
}

const ICON_BY_TYPE: Record<Pattern["type"], typeof AlertCircle> = {
  emotion_cluster: Users,
  department_drop: TrendingDown,
  complaint_category: AlertCircle,
  at_risk_individual: ShieldAlert,
};

const SEVERITY_STYLE: Record<Pattern["severity"], string> = {
  high: "border-danger/35 bg-danger-soft/30 text-danger",
  medium: "border-warning/30 bg-warning-soft/30 text-warning",
  low: "border-border bg-secondary/40 text-muted-foreground",
};

export function PatternsCard({ days = 14 }: { days?: number }) {
  const [data, setData] = useState<PatternsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getJson<PatternsResponse>(`/api/v1/analytics/patterns?days=${days}`).then((d) => {
      if (cancelled) return;
      setData(d);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [days]);

  const patterns = data?.patterns ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start gap-3 mb-4">
        <div className="size-9 rounded-xl grid place-items-center text-indigo-500 bg-indigo-500/10 shrink-0">
          <Users className="size-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            Patterns &amp; recommendations
          </div>
          <div className="text-sm font-medium mt-0.5">
            {loading ? "Scanning…" : `Last ${data?.window_days ?? days} days`}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-6 text-center text-sm text-muted-foreground">Scanning…</div>
      ) : patterns.length === 0 ? (
        <div className="py-6 text-center text-sm text-muted-foreground">
          No cross-employee patterns yet. MARK surfaces clusters here as they emerge —
          recurring negative emotions, department sentiment drops, complaint themes, or
          individuals trending high-risk.
        </div>
      ) : (
        <ul className="space-y-3">
          {patterns.map((p, i) => {
            const Icon = ICON_BY_TYPE[p.type] ?? AlertCircle;
            return (
              <li
                key={`${p.type}-${i}`}
                className="rounded-xl border border-border/70 bg-secondary/30 p-3 flex items-start gap-3"
              >
                <span
                  className={cn(
                    "size-7 rounded-md grid place-items-center shrink-0 border",
                    SEVERITY_STYLE[p.severity],
                  )}
                >
                  <Icon className="size-3.5" />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium leading-tight">{p.label}</span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider border",
                        SEVERITY_STYLE[p.severity],
                      )}
                    >
                      {p.severity}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 flex items-start gap-1">
                    <ArrowRight className="size-3 mt-0.5 shrink-0" />
                    <span>{p.recommendation}</span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
