import { AppLayout } from "@/components/layout/AppLayout";
import { Sparkline, BarMini } from "@/components/charts";
import { EmotionMixTrendCard } from "@/components/analytics/EmotionMixTrendCard";
import { AlertsPanelCard } from "@/components/dashboard/AlertsPanelCard";
import { AtRiskEmployeesCard } from "@/components/dashboard/AtRiskEmployeesCard";
import { DepartmentHeatmapCard } from "@/components/dashboard/DepartmentHeatmapCard";
import { KpiStatsRow } from "@/components/dashboard/KpiStatsRow";
import { SentimentTrendsCard } from "@/components/dashboard/SentimentTrendsCard";
import { getDashboardData, getRecentActivity } from "@/lib/services";
import type { ActivityItem } from "@/lib/services";
import {
  ArrowUpRight,
  AlertTriangle,
  TrendingDown,
  Heart,
  Sparkles,
  Users,
  Zap,
  Moon,
  RadioTower,
  Layers,
} from "lucide-react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";
import { subscribeToSse } from "@/lib/api/client";
import { useChat } from "@/contexts/ChatContext";

const toneStyles = {
  positive: { ring: "ring-emerald/30", icon: Heart, iconCls: "text-emerald bg-emerald-soft" },
  watch: { ring: "ring-warning/30", icon: TrendingDown, iconCls: "text-warning bg-warning-soft" },
  at_risk: { ring: "ring-danger/30", icon: AlertTriangle, iconCls: "text-danger bg-danger-soft" },
  neutral: { ring: "ring-border", icon: Sparkles, iconCls: "text-accent bg-accent-soft" },
};

export default function Dashboard() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getDashboardData>>>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const { open, send } = useChat();

  useEffect(() => {
    const refreshDashboard = () => {
      void getDashboardData().then(setData);
      void getRecentActivity().then(setActivity);
    };

    refreshDashboard();
    const unsubscribe = subscribeToSse("/api/v1/realtime/hr/stream", {
      onEvent: (eventType) => {
        if (eventType === "hr_snapshot") refreshDashboard();
      },
    });
    const refreshTimer = window.setInterval(refreshDashboard, 45000);

    return () => {
      unsubscribe();
      window.clearInterval(refreshTimer);
    };
  }, []);

  const sentimentTrend = useMemo(
    () =>
      (data?.sentiment || []).map((point, index) => ({
        day: String(index + 1),
        value: Math.round(point.positive),
      })),
    [data?.sentiment],
  );

  const ticketTrend = useMemo(
    () =>
      (data?.sentiment || []).map((point, index) => ({
        day: String(index + 1),
        value: Math.round(point.negative),
      })),
    [data?.sentiment],
  );

  return (
    <AppLayout title="Pulse" subtitle="What's actually happening with your people, in plain language.">
      <div className="px-6 lg:px-10 py-8 max-w-7xl space-y-8">
        {/* Headline */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">This week</div>
          <h2 className="mt-2 font-display text-4xl tracking-tight max-w-3xl text-balance">Team pulse from live analytics.</h2>
          <p className="mt-3 text-muted-foreground max-w-2xl">
            {data?.aiSummary?.trim()
              ? data.aiSummary
              : data
                ? "Insights are based on current backend signals."
                : "Dashboard data unavailable until analytics endpoint is ready."}
          </p>
          {data?.last_chat_sentiment_at && (
            <p className="mt-1 text-[11px] text-muted-foreground/70">
              Last updated from chat: {new Date(data.last_chat_sentiment_at).toLocaleString()}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/employees?risk=at_risk" className="text-xs px-3 py-1.5 rounded-full border border-border bg-card hover:bg-secondary transition-colors">
              Open at-risk employees
            </Link>
            <Link to="/employees?risk=watch" className="text-xs px-3 py-1.5 rounded-full border border-border bg-card hover:bg-secondary transition-colors">
              Open watchlist
            </Link>
            <Link to="/tickets?status=escalated&priority=critical" className="text-xs px-3 py-1.5 rounded-full border border-border bg-card hover:bg-secondary transition-colors">
              Escalated critical tickets
            </Link>
          </div>
        </motion.div>

        {(data?.managerPattern || (data?.employeeHighlights?.length ?? 0) > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="space-y-4"
          >
            {data?.managerPattern && (
              <div className="rounded-2xl border border-warning/35 bg-warning-soft/25 p-5 ring-1 ring-warning/20">
                <div className="flex items-start gap-4">
                  <div className="size-10 rounded-xl grid place-items-center shrink-0 text-warning bg-warning-soft">
                    <AlertTriangle className="size-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Manager pattern</div>
                    <p className="mt-1.5 text-sm text-foreground">
                      <span className="font-medium">{data.managerPattern.count} signals</span> in the last week point to{" "}
                      <span className="font-medium">manager-related stress</span> on teams reporting to{" "}
                      <span className="font-medium">{data.managerPattern.manager}</span>.
                    </p>
                    <Link
                      to={`/employees?managerId=${encodeURIComponent(data.managerPattern.manager_id)}`}
                      className="mt-3 inline-flex items-center gap-1.5 text-sm text-foreground hover:text-accent transition-colors"
                    >
                      Open team in directory <ArrowUpRight className="size-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            )}

            {(data?.employeeHighlights?.length ?? 0) > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Users className="size-4 text-muted-foreground" />
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">People spotlight</div>
                    <div className="text-sm font-medium mt-0.5">Signals worth a conversation</div>
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  {(data?.employeeHighlights ?? []).map((h, i) => (
                    <motion.div
                      key={h.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35, delay: i * 0.04 }}
                    >
                      <div className="block rounded-2xl border border-border bg-card p-5 hover:shadow-elevated transition-shadow h-full">
                        {(() => {
                          const staleSignalDays = Number(data?.sentiment_stale_days ?? 7);
                          const lastTs = h.sentiment_last_updated_at ? new Date(h.sentiment_last_updated_at) : null;
                          const ageMs = lastTs ? Date.now() - lastTs.getTime() : 0;
                          const stale = !lastTs || Number.isNaN(lastTs.getTime()) || ageMs > staleSignalDays * 24 * 60 * 60 * 1000;
                          return stale ? (
                            <div className="mb-2 text-[10px] uppercase tracking-wide px-2 py-1 rounded-md bg-warning-soft text-warning font-medium inline-flex items-center gap-1">
                              Stale signal {lastTs ? `(>${staleSignalDays}d)` : "(no recent sentiment)"}
                            </div>
                          ) : null;
                        })()}
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium">{h.name}</div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                              Risk {h.risk_score}/100 · {h.risk_label} · sentiment {Math.round(h.sentiment_score)}%
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-1 justify-end shrink-0">
                            {h.spike_alert && (
                              <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-md bg-danger-soft text-danger font-medium inline-flex items-center gap-0.5">
                                <Zap className="size-3" /> Spike
                              </span>
                            )}
                            {h.silent_risk && (
                              <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-md bg-warning-soft text-warning font-medium inline-flex items-center gap-0.5">
                                <Moon className="size-3" /> Quiet risk
                              </span>
                            )}
                            {h.sustained_risk_pattern && (
                              <span
                                className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-md bg-danger-soft text-danger font-medium inline-flex items-center gap-0.5"
                                title={
                                  h.negative_turns_in_window != null && data
                                    ? `${h.negative_turns_in_window} negative signals in the last ${data.sustained_risk_window_days} days (alert threshold: ${data.sustained_risk_min_negative_turns})`
                                    : "Repeated negative chat signals — HR notified"
                                }
                              >
                                <RadioTower className="size-3" /> Sustained risk
                              </span>
                            )}
                          </div>
                        </div>
                        {h.top_topic && (
                          <div className="mt-2 text-xs text-muted-foreground">
                            Top topic: <span className="text-foreground">{h.top_topic}</span>
                          </div>
                        )}
                        {h.sentiment_last_updated_at && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            Sentiment updated:{" "}
                            <span className="text-foreground">
                              {new Date(h.sentiment_last_updated_at).toLocaleString()}
                            </span>
                          </div>
                        )}
                        {h.sentiment_confidence_band && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            Trend confidence:{" "}
                            <span
                              className={
                                h.sentiment_confidence_band === "high"
                                  ? "text-emerald"
                                  : h.sentiment_confidence_band === "medium"
                                    ? "text-warning"
                                    : "text-danger"
                              }
                            >
                              {h.sentiment_confidence_band}
                            </span>
                            {h.sentiment_confidence != null ? ` (${Math.round(h.sentiment_confidence * 100)}%)` : ""}
                          </div>
                        )}
                        {h.narrative.length > 0 && (
                          <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground border-t border-border pt-3">
                            {h.narrative.slice(0, 4).map((line, j) => (
                              <li key={`${h.id}-n-${j}`} className="pl-3 border-l-2 border-accent/40">
                                {line}
                              </li>
                            ))}
                          </ul>
                        )}
                        <div className="mt-4 flex flex-wrap gap-2">
                          <Link
                            to={`/employees/${h.id}`}
                            className="text-xs px-2.5 py-1 rounded-md border border-border bg-card hover:bg-secondary transition-colors inline-flex items-center gap-1"
                          >
                            Profile <ArrowUpRight className="size-3" />
                          </Link>
                          <Link
                            to={`/tickets?q=${encodeURIComponent(h.name)}`}
                            className="text-xs px-2.5 py-1 rounded-md border border-border bg-card hover:bg-secondary transition-colors"
                          >
                            Open tickets
                          </Link>
                          <button
                            type="button"
                            onClick={() => {
                              open();
                              void send(`Draft a check-in plan for ${h.name} based on current risk signals.`);
                            }}
                            className="text-xs px-2.5 py-1 rounded-md border border-border bg-card hover:bg-secondary transition-colors"
                          >
                            Schedule check-in
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        <KpiStatsRow />

        {/* KPI row */}
        <div className="grid md:grid-cols-4 gap-4">
          <Kpi
            label="Team morale"
            value={data ? String(Math.round(data.metrics.engagement_score)) : "—"}
            trend="from analytics"
            tone="watch"
            chart={<Sparkline data={sentimentTrend} color="hsl(var(--warning))" />}
            to="/employees?risk=watch"
          />
          <Kpi
            label="Open tickets"
            value={data ? String(data.metrics.open_tickets) : "—"}
            trend="currently open"
            tone="neutral"
            chart={<BarMini data={ticketTrend.slice(0, 5)} />}
            to="/tickets?status=open"
          />
          <Kpi
            label="Resolution rate"
            value={data ? `${Math.round(data.metrics.resolution_rate * 100)}%` : "—"}
            trend="from backend"
            tone="positive"
            chart={<BarMini data={ticketTrend} />}
            to="/tickets?status=resolved"
          />
          <Kpi
            label="Ticket volume"
            value={data ? String(data.metrics.total_tickets) : "—"}
            trend="total tickets"
            tone="neutral"
            chart={<BarMini data={ticketTrend} />}
            to="/tickets"
          />
        </div>

        <SentimentTrendsCard />

        <DepartmentHeatmapCard />

        <div className="grid lg:grid-cols-2 gap-4">
          <AtRiskEmployeesCard limit={10} />
          <AlertsPanelCard limit={30} />
        </div>

        <EmotionMixTrendCard
          points={data?.emotions ?? []}
          eyebrow="Emotion mix trend"
          title="Stress, frustration, and anxiety trend (last 14 days)"
        />

        <EmotionMixTrendCard
          variant="sources"
          points={(data?.classifier_source_trend ?? []).map((p) => ({ date: p.date, sources: p.sources }))}
          eyebrow="Classifier drift"
          title="LLM vs lexicon vs hybrid mix (last 14 days)"
          emptyMessage="No classifier history yet — logs populate as employees chat."
        />

        {data?.sentiment_source_drift && data.sentiment_source_drift.total > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="rounded-2xl border border-border bg-card p-5 ring-1 ring-border/60"
          >
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-xl grid place-items-center shrink-0 bg-accent-soft text-accent">
                <Layers className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Classifier mix</div>
                <p className="text-sm text-muted-foreground mt-1">
                  How employee chat sentiment was produced in the last {data.sentiment_source_drift.window_days} days (
                  {data.sentiment_source_drift.total} messages logged).
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(() => {
                    const order = ["llm", "hybrid", "lexicon", "provided", "unknown"] as const;
                    const labels: Record<string, string> = {
                      llm: "LLM",
                      hybrid: "Hybrid",
                      lexicon: "Lexicon",
                      provided: "Provided",
                      unknown: "Unknown",
                    };
                    const pct = data.sentiment_source_drift.pct_by_source;
                    const by = data.sentiment_source_drift.by_source;
                    const rank = (k: string) => {
                      const i = order.indexOf(k as (typeof order)[number]);
                      return i === -1 ? 100 : i;
                    };
                    const sorted = Object.keys(by).sort((a, b) => rank(a) - rank(b));
                    return sorted.map((key) => (
                      <span
                        key={key}
                        className="text-xs px-2.5 py-1 rounded-md border border-border bg-secondary/60 text-foreground"
                      >
                        {labels[key] ?? key}{" "}
                        <span className="text-muted-foreground">
                          ({by[key] ?? 0} · {pct[key] ?? 0}%)
                        </span>
                      </span>
                    ));
                  })()}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Insights */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">What MARK noticed</div>
              <div className="font-medium mt-1">Insights, not numbers</div>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {(data?.insights || []).slice(0, 5).map((ins, i) => {
              const t = toneStyles[ins.tone];
              const Icon = t.icon;
              return (
                <motion.div
                  key={ins.id}
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.05 }}
                  className={cn("rounded-2xl border border-border bg-card p-5 ring-1 ring-transparent hover:shadow-elevated transition-shadow", t.ring)}
                >
                  <div className="flex items-start gap-4">
                    <div className={cn("size-10 rounded-xl grid place-items-center shrink-0", t.iconCls)}>
                      <Icon className="size-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-balance">{ins.title}</div>
                      <p className="text-sm text-muted-foreground mt-1.5">{ins.detail}</p>
                      <Link to={ins.tone === "at_risk" ? "/employees?risk=at_risk" : ins.route} className="mt-3 inline-flex items-center gap-1.5 text-sm text-foreground hover:text-accent transition-colors">
                        {ins.action} <ArrowUpRight className="size-3.5" />
                      </Link>
                    </div>
                  </div>
                </motion.div>
              );
            })}
            {!data?.insights?.length && (
              <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
                {data?.employeeHighlights?.length
                  ? "No separate insight records yet — see People spotlight above for live signals."
                  : "Insight data unavailable until endpoint exists."}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Recent activity</div>
            <Link to="/tickets" className="text-xs text-accent hover:underline">
              View all tickets →
            </Link>
          </div>
          {activity.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent ticket activity yet.</p>
          ) : (
            <ul className="divide-y divide-border">
              {activity.map((a, i) => (
                <li key={`${a.text}-${i}`} className="py-3 flex items-center gap-3">
                  <div className="size-2 rounded-full bg-accent shrink-0" />
                  <div className="text-sm flex-1">{a.text}</div>
                  <span className={cn("text-[11px] px-2 py-0.5 rounded-md font-medium", a.tagCls)}>{a.tag}</span>
                  <div className="text-[11px] text-muted-foreground w-14 text-right">{a.time}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

function Kpi({
  label,
  value,
  trend,
  tone,
  chart,
  to,
}: {
  label: string;
  value: string;
  trend: string;
  tone: keyof typeof toneStyles;
  chart: React.ReactNode;
  to: string;
}) {
  const t = toneStyles[tone];
  return (
    <Link to={to} className="rounded-2xl border border-border bg-card p-5 flex flex-col gap-3 hover:shadow-elevated transition-shadow">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div>
        <div className="font-display text-2xl tracking-tight">{value}</div>
        <div className={cn("text-xs mt-1", tone === "at_risk" ? "text-danger" : tone === "watch" ? "text-warning" : tone === "positive" ? "text-emerald" : "text-muted-foreground")}>{trend}</div>
      </div>
      <div className="mt-auto">{chart}</div>
    </Link>
  );
}
