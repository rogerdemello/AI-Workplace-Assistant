import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { EmotionMixTrendCard } from "@/components/analytics/EmotionMixTrendCard";
import { Avatar, SentimentBadge } from "@/components/ui-bits";
import { AlertTriangle, ArrowRight, Sparkles, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { Link } from "react-router-dom";
import { useChat } from "@/contexts/ChatContext";
import {
  approveLeaveRequest,
  getManagerPageClassifierTrend,
  getManagerPageEmotionTrend,
  getManagerSummary,
  getManagerTeam,
  listLeaveRequests,
  rejectLeaveRequest,
  type LeaveRow,
  type ManagerSummary,
} from "@/lib/services";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { Employee } from "@/lib/domain-types";
import { useAuth } from "@/contexts/AuthContext";

export default function Manager() {
  const { open, send } = useChat();
  const { session } = useAuth();
  const [team, setTeam] = useState<Employee[]>([]);
  const [pendingLeave, setPendingLeave] = useState<LeaveRow[]>([]);
  const [summary, setSummary] = useState<ManagerSummary | null>(null);
  const [busyLeaveId, setBusyLeaveId] = useState<string | null>(null);
  const [emotionTrend, setEmotionTrend] = useState<Array<{ date: string; emotions: Record<string, number> }>>([]);
  const [classifierTrend, setClassifierTrend] = useState<Array<{ date: string; sources: Record<string, number> }>>([]);

  const loadPending = () => {
    void listLeaveRequests("pending").then(setPendingLeave);
  };

  useEffect(() => {
    getManagerTeam().then(setTeam);
    getManagerSummary().then(setSummary);
    loadPending();
  }, []);

  useEffect(() => {
    void getManagerPageEmotionTrend(session?.role, 14).then(setEmotionTrend);
    void getManagerPageClassifierTrend(session?.role, 14).then(setClassifierTrend);
  }, [session?.role]);

  const teamAttention = team
    .filter((member) => member.sentiment === "watch" || member.sentiment === "at_risk" || member.riskScore >= 60)
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 4);
  const trendScore = team.reduce((acc, member) => {
    if (member.sentimentTrend === "up") return acc + 1;
    if (member.sentimentTrend === "down") return acc - 1;
    return acc;
  }, 0);
  const trendLabel = trendScore > 0 ? "improving" : trendScore < 0 ? "declining" : "stable";
  const TrendIcon = trendScore > 0 ? TrendingUp : trendScore < 0 ? TrendingDown : Minus;
  const riskTrendLabel = trendScore > 0 ? "declining risk" : trendScore < 0 ? "rising risk" : "stable risk";
  const RiskTrendIcon = trendScore > 0 ? TrendingDown : trendScore < 0 ? TrendingUp : Minus;

  return (
    <AppLayout title="Manager" subtitle="Your team's health and what needs you today">
      <div className="px-6 lg:px-10 py-8 max-w-6xl space-y-8">
        <div className="rounded-2xl bg-ink text-primary-foreground p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-aurora opacity-60" />
          <div className="relative grid md:grid-cols-3 gap-6 items-center">
            <div className="md:col-span-2">
              <div className="text-xs uppercase tracking-[0.18em] text-primary-foreground/60">This week with your team</div>
              <h2 className="mt-2 font-display text-2xl text-balance">Manager cockpit</h2>
              <p className="mt-2 text-sm text-primary-foreground/70">
                Direct reports come from org structure. Pending leave for your team (or organization-wide for HR) appears below.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                open();
                void send("How is my team doing this week?");
              }}
              className="justify-self-start md:justify-self-end inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-accent-foreground font-medium text-sm"
            >
              <Sparkles className="size-4" /> Ask MARK
            </button>
          </div>
        </div>

        <div className="grid md:grid-cols-5 gap-4">
          <ManagerKpi label="Team size" value={summary ? String(summary.team_size) : "—"} />
          <ManagerKpi
            label="High risk"
            value={summary ? String(summary.high_risk_count ?? summary.at_risk_members) : "—"}
            tone="danger"
          />
          <ManagerKpi label="Watch list" value={summary ? String(summary.watch_members) : "—"} tone="warning" />
          <ManagerKpi label="Pending leave" value={String(pendingLeave.length)} />
          <ManagerKpi label="Open team tickets" value={summary ? String(summary.open_team_tickets) : "—"} />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <ManagerKpi
            label="Avg team sentiment"
            value={summary ? `${Math.round(summary.avg_team_sentiment ?? 0)}/100` : "—"}
            tone={summary && (summary.avg_team_sentiment ?? 0) < 45 ? "danger" : "neutral"}
            trend={trendLabel}
            trendIcon={TrendIcon}
          />
          <ManagerKpi
            label="Avg team risk"
            value={summary ? `${Math.round(summary.avg_team_risk ?? 0)}/100` : "—"}
            tone={summary && (summary.avg_team_risk ?? 0) >= 60 ? "danger" : summary && (summary.avg_team_risk ?? 0) >= 40 ? "warning" : "neutral"}
            trend={riskTrendLabel}
            trendIcon={RiskTrendIcon}
          />
        </div>

        <EmotionMixTrendCard
          points={emotionTrend}
          eyebrow="Team emotion signals"
          title={
            session?.role === "hr"
              ? "Stress, frustration, and anxiety (organization preview)"
              : "Stress, frustration, and anxiety (your direct reports)"
          }
          emptyMessage={
            session?.role === "hr"
              ? "No emotion logs in this window, or analytics unavailable."
              : "No emotion signals from your team in the last 14 days yet."
          }
        />

        <EmotionMixTrendCard
          variant="sources"
          points={classifierTrend.map((p) => ({ date: p.date, sources: p.sources }))}
          eyebrow="Classifier mix"
          title={
            session?.role === "hr"
              ? "LLM vs lexicon vs hybrid (organization preview)"
              : "How team sentiment was classified (your direct reports)"
          }
          emptyMessage={
            session?.role === "hr"
              ? "No classifier history in this window."
              : "No classifier history from your team in the last 14 days yet."
          }
        />

        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Needs your decision</div>
              <div className="font-medium mt-1">Leave approvals</div>
            </div>
          </div>
          {pendingLeave.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pending leave requests.</p>
          ) : (
            <ul className="space-y-3">
              {pendingLeave.map((lv) => (
                <li key={lv.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl border border-border bg-secondary/30">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{lv.employeeName ?? "Employee"}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {lv.startDate} → {lv.endDate} · {lv.leaveType.replace(/_/g, " ")}
                    </div>
                    {lv.reason && <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{lv.reason}</div>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      type="button"
                      size="sm"
                      disabled={busyLeaveId === lv.id}
                      onClick={async () => {
                        setBusyLeaveId(lv.id);
                        const done = await approveLeaveRequest(lv.id);
                        setBusyLeaveId(null);
                        if (!done) {
                          toast.error("Could not approve this request.");
                          return;
                        }
                        toast.success("Leave approved.");
                        loadPending();
                      }}
                    >
                      Approve
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busyLeaveId === lv.id}
                      onClick={async () => {
                        setBusyLeaveId(lv.id);
                        const done = await rejectLeaveRequest(lv.id);
                        setBusyLeaveId(null);
                        if (!done) {
                          toast.error("Could not reject this request.");
                          return;
                        }
                        toast.success("Leave rejected.");
                        loadPending();
                      }}
                    >
                      Reject
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Attention needed</div>
              <div className="font-medium mt-1">Who needs support this week</div>
            </div>
          </div>
          {teamAttention.length === 0 ? (
            <p className="text-sm text-muted-foreground">No critical team alerts right now.</p>
          ) : (
            <ul className="space-y-3">
              {teamAttention.map((member) => (
                <li key={member.id} className="flex items-center justify-between gap-3 p-3 rounded-xl border border-border bg-secondary/20">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{member.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Sentiment: {member.sentiment.replace("_", " ")} · Risk {member.riskScore}/100
                    </div>
                  {member.topEmotion ? (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Dominant emotion: {member.topEmotion.replace("_", " ")}
                    </div>
                  ) : null}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      open();
                      void send(`Help me support ${member.name} on my team this week`);
                    }}
                  >
                    Coach me
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-xl bg-warning-soft text-warning grid place-items-center">
                <AlertTriangle className="size-4" />
              </div>
              <div className="flex-1">
                <div className="font-medium">1:1 prep</div>
                <p className="text-sm text-muted-foreground mt-1">Ask MARK for talking points before difficult conversations.</p>
                <button
                  type="button"
                  onClick={() => {
                    open();
                    void send("Help me prep for a difficult 1:1");
                  }}
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent"
                >
                  Prep with MARK <ArrowRight className="size-3.5" />
                </button>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-xl bg-emerald-soft text-emerald grid place-items-center">
                <Sparkles className="size-4" />
              </div>
              <div className="flex-1">
                <div className="font-medium">Recognition</div>
                <p className="text-sm text-muted-foreground mt-1">Draft a concise recognition note for your team channel.</p>
                <button
                  type="button"
                  onClick={() => {
                    open();
                    void send("Help me write a short recognition note for my team");
                  }}
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent"
                >
                  Draft it <ArrowRight className="size-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-4">Your team</div>
          <div className="grid md:grid-cols-3 gap-4">
            {team.map((e) => {
              const inner = (
                <>
                  <div className="flex items-center gap-3">
                    <Avatar initials={e.initials} size="md" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{e.name}</div>
                      <div className="text-xs text-muted-foreground truncate">{e.role}</div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <SentimentBadge sentiment={e.sentiment} />
                    <div className="text-xs text-muted-foreground">{e.leaveBalance} leave days</div>
                  </div>
                </>
              );
              return session?.role === "hr" ? (
                <Link key={e.id} to={`/employees/${e.id}`} className="rounded-2xl border border-border bg-card p-5 hover:shadow-elevated transition-shadow">
                  {inner}
                </Link>
              ) : (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => {
                    open();
                    void send(`Help me support ${e.name} on my team`);
                  }}
                  className="rounded-2xl border border-border bg-card p-5 hover:shadow-elevated transition-shadow text-left w-full"
                >
                  {inner}
                </button>
              );
            })}
            {team.length === 0 && (
              <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground md:col-span-3">
                No direct reports found. When users have <span className="font-mono text-xs">manager_id</span> set to you in the directory, they appear here.
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

function ManagerKpi({
  label,
  value,
  tone = "neutral",
  trend,
  trendIcon: TrendIcon,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "danger";
  trend?: string;
  trendIcon?: typeof TrendingUp;
}) {
  const valueClass =
    tone === "danger" ? "text-danger" : tone === "warning" ? "text-warning" : "text-foreground";
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-2 font-display text-2xl tracking-tight ${valueClass}`}>{value}</div>
      {trend && TrendIcon ? (
        <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <TrendIcon className="size-3.5" />
          <span>{trend}</span>
        </div>
      ) : null}
    </div>
  );
}
