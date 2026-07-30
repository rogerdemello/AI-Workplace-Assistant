import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import { getJson } from "@/lib/api/client";

interface TrendPoint {
  date: string;
  positive: number;
  neutral: number;
  negative: number;
}

const RANGE_OPTIONS = [
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
  { days: 90, label: "90d" },
];

export function SentimentTrendsCard() {
  const [days, setDays] = useState(7);
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getJson<TrendPoint[]>(`/api/v1/analytics/sentiment?days=${days}`).then((data) => {
      if (cancelled) return;
      setPoints(Array.isArray(data) ? data : []);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [days]);

  const formatted = useMemo(
    () =>
      points.map((p) => ({
        ...p,
        // MM-DD for compact axis labels
        label: p.date.length === 10 ? p.date.slice(5) : p.date,
      })),
    [points],
  );

  const hasData = formatted.some((p) => p.positive + p.neutral + p.negative > 0);

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Sentiment trend</div>
          <div className="text-sm font-medium mt-0.5">Share of positive / neutral / negative messages</div>
        </div>
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
              onClick={() => setDays(opt.days)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-md transition-colors",
                days === opt.days
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-56">
        {loading ? (
          <div className="h-full grid place-items-center text-sm text-muted-foreground">Loading…</div>
        ) : !hasData ? (
          <div className="h-full grid place-items-center text-sm text-muted-foreground">
            No sentiment data in this window yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={formatted} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="posGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--emerald))" stopOpacity={0.7} />
                  <stop offset="100%" stopColor="hsl(var(--emerald))" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="neuGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="negGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--danger))" stopOpacity={0.7} />
                  <stop offset="100%" stopColor="hsl(var(--danger))" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                axisLine={false}
                tickLine={false}
                width={28}
                unit="%"
              />
              <Tooltip
                cursor={{ stroke: "hsl(var(--border))", strokeWidth: 1 }}
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(v: number, name: string) => [`${v.toFixed(1)}%`, name]}
              />
              <Area
                type="monotone"
                dataKey="positive"
                name="Positive"
                stroke="hsl(var(--emerald))"
                strokeWidth={1.5}
                fill="url(#posGrad)"
                stackId="1"
              />
              <Area
                type="monotone"
                dataKey="neutral"
                name="Neutral"
                stroke="hsl(var(--muted-foreground))"
                strokeWidth={1.5}
                fill="url(#neuGrad)"
                stackId="1"
              />
              <Area
                type="monotone"
                dataKey="negative"
                name="Negative"
                stroke="hsl(var(--danger))"
                strokeWidth={1.5}
                fill="url(#negGrad)"
                stackId="1"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        <LegendDot color="hsl(var(--emerald))" label="Positive" />
        <LegendDot color="hsl(var(--muted-foreground))" label="Neutral" />
        <LegendDot color="hsl(var(--danger))" label="Negative" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="inline-block size-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </div>
  );
}
