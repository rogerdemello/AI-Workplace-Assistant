import { useEffect, useState } from "react";
import { HeartPulse, Smile, Meh, Frown } from "lucide-react";
import { getJson } from "@/lib/api/client";

interface PulseSummary {
  window_days: number;
  questions_asked: number;
  replies_received: number;
  response_rate: number;
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
    average_score_0_100: number | null;
  };
  top_emotion: string | null;
}

export function PulseSummaryCard({ days = 30 }: { days?: number }) {
  const [data, setData] = useState<PulseSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getJson<PulseSummary>(`/api/v1/analytics/pulse-summary?days=${days}`).then((d) => {
      if (cancelled) return;
      setData(d);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [days]);

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start gap-3 mb-4">
        <div className="size-9 rounded-xl grid place-items-center text-rose-500 bg-rose-500/10 shrink-0">
          <HeartPulse className="size-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Pulse check-ins</div>
          <div className="text-sm font-medium mt-0.5">
            {loading ? "Loading…" : `Last ${data?.window_days ?? days} days`}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-6 text-center text-sm text-muted-foreground">Loading…</div>
      ) : !data || data.questions_asked === 0 ? (
        <div className="py-6 text-center text-sm text-muted-foreground">
          MARK hasn't asked any pulse questions in this window yet.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Asked" value={data.questions_asked} />
            <Stat label="Replies" value={data.replies_received} />
            <Stat label="Response" value={`${Math.round(data.response_rate * 100)}%`} />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <SentimentChip
              icon={<Smile className="size-3.5" />}
              label="Positive"
              count={data.sentiment.positive}
              tone="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
            />
            <SentimentChip
              icon={<Meh className="size-3.5" />}
              label="Neutral"
              count={data.sentiment.neutral}
              tone="border-border bg-secondary/50 text-muted-foreground"
            />
            <SentimentChip
              icon={<Frown className="size-3.5" />}
              label="Negative"
              count={data.sentiment.negative}
              tone="border-danger/30 bg-danger-soft/30 text-danger"
            />
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            {data.top_emotion && (
              <div>
                Top emotion: <span className="text-foreground font-medium">{data.top_emotion}</span>
              </div>
            )}
            {data.sentiment.average_score_0_100 !== null && (
              <div>
                Avg sentiment score:{" "}
                <span className="text-foreground font-medium">
                  {data.sentiment.average_score_0_100}/100
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border/70 bg-secondary/30 p-3 text-center">
      <div className="text-lg font-semibold leading-tight">{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function SentimentChip({
  icon,
  label,
  count,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
  tone: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border ${tone}`}
    >
      {icon} {label} <span className="opacity-80">{count}</span>
    </span>
  );
}
