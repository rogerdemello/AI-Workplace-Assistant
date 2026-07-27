import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { OffboardingClearanceCard } from "@/components/employee/OffboardingClearanceCard";
import { getEmployeeTimeline, getTickets, getUserDetail } from "@/lib/services";
import type { UserDetail } from "@/lib/services";
import type { Ticket } from "@/lib/domain-types";
import { Avatar, SentimentBadge, StatusPill, PriorityPill } from "@/components/ui-bits";
import { ArrowLeft, Calendar, MapPin, Mail, Sparkles, Zap, Moon, Pencil } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";
import { useAuth } from "@/contexts/AuthContext";
import { EditProfileDialog } from "@/components/EditProfileDialog";

type LoadState = "loading" | "ready" | "missing";

export default function EmployeeProfile() {
  const { id } = useParams();
  const [emp, setEmp] = useState<UserDetail | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [timeline, setTimeline] = useState<Array<{ date: string; text: string; tone: string }>>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [editOpen, setEditOpen] = useState(false);
  const { open, send } = useChat();
  const { session } = useAuth();

  const refreshProfile = () => {
    if (!id) return;
    getUserDetail(id).then((row) => {
      if (row) setEmp(row);
    });
  };

  useEffect(() => {
    if (!id) {
      setLoadState("missing");
      return;
    }
    setLoadState("loading");
    getUserDetail(id)
      .then((row) => {
        if (!row) {
          setEmp(null);
          setLoadState("missing");
          return;
        }
        setEmp(row);
        setLoadState("ready");
      })
      .catch(() => {
        setEmp(null);
        setLoadState("missing");
      });
    getTickets().then((all) => setTickets(all.filter((t) => t.raisedBy === id)));
    getEmployeeTimeline(id).then(setTimeline);
  }, [id]);

  const isSelf = Boolean(emp && session && (session.id === emp.id || session.email === emp.email));

  if (!id || loadState === "missing") {
    return (
      <AppLayout title="Employee">
        <div className="p-10 text-sm text-muted-foreground">
          {!id ? "Invalid link." : "This employee could not be found."}
        </div>
      </AppLayout>
    );
  }

  if (loadState === "loading" || !emp) {
    return (
      <AppLayout title="Loading…">
        <div className="p-10 text-sm text-muted-foreground">Loading…</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="px-6 lg:px-10 py-8 max-w-6xl">
        <Link
          to="/employees"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="size-3.5" /> Back to employees
        </Link>

        <div className="rounded-2xl border border-border bg-card p-6 flex flex-col md:flex-row md:items-center gap-6">
          <Avatar initials={emp.initials} size="lg" tone="teal" />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-display text-3xl tracking-tight">{emp.name}</h2>
              <SentimentBadge sentiment={emp.sentiment} />
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {emp.role} · {emp.department}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Mail className="size-3.5" />
                {emp.email || "—"}
              </span>
              <span className="flex items-center gap-1.5">
                <MapPin className="size-3.5" />
                {emp.location}
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar className="size-3.5" />
                {emp.joinedAt ? `Joined ${emp.joinedAt}` : "Joined —"}
              </span>
            </div>
            {emp.managerName && <div className="mt-2 text-xs text-muted-foreground">Reports to {emp.managerName}</div>}
          </div>
          <div className="flex flex-col gap-2 md:flex-row md:items-center">
            {isSelf && (
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-card text-foreground text-sm font-medium hover:bg-secondary transition"
              >
                <Pencil className="size-4" /> Edit profile
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                open();
                void send(`Tell me about ${emp.name}`);
              }}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ink text-primary-foreground text-sm font-medium"
            >
              <Sparkles className="size-4" /> Ask MARK about {emp.name.split(" ")[0]}
            </button>
          </div>
        </div>

        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <Stat
            label="Sentiment"
            value={`${Math.round(emp.sentimentScore ?? 50)}%`}
            hint={`${formatTrendArrow(emp.sentimentTrend)} ${formatTrendWord(emp.sentimentTrend)} · Δ ${emp.sentimentDelta ?? 0}`}
          />
          <Stat
            label="Risk score"
            value={`${emp.calibratedRiskScore ?? emp.riskScore}/100`}
            hint={
              `${emp.riskLabel ?? deriveRiskLabel(emp.riskScore)} — ${
                emp.riskScore > 60
                  ? "needs attention"
                  : emp.riskScore > 35
                    ? "watch closely"
                    : "healthy"
              }`
            }
          />
          <Stat
            label="Leave balance"
            value={`${emp.leaveBalance} days`}
            hint={
              emp.annualLeaveDays != null && emp.usedLeaveDaysYtd != null
                ? `${emp.usedLeaveDaysYtd} used YTD · ${emp.annualLeaveDays} annual entitlement`
                : "From directory"
            }
          />
          <Stat
            label="Open tickets"
            value={String(tickets.filter((t) => t.status !== "resolved").length)}
            hint={`${tickets.length} total`}
          />
        </div>

        {(emp.narrative?.length || emp.spikeAlert || emp.silentRisk || emp.topTopic) && (
          <div className="mt-6 rounded-2xl border border-border bg-card p-6">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Conversation signals</div>
            <div className="flex flex-wrap gap-2 mb-4">
              {emp.spikeAlert && (
                <span className="text-xs px-2.5 py-1 rounded-md bg-danger-soft text-danger font-medium inline-flex items-center gap-1">
                  <Zap className="size-3.5" /> Spike alert
                </span>
              )}
              {emp.silentRisk && (
                <span className="text-xs px-2.5 py-1 rounded-md bg-warning-soft text-warning font-medium inline-flex items-center gap-1">
                  <Moon className="size-3.5" /> Quiet risk
                </span>
              )}
              {emp.topTopic && (
                <span className="text-xs px-2.5 py-1 rounded-md bg-secondary text-foreground">
                  Top topic: {emp.topTopic}
                </span>
              )}
              {emp.complaints5d != null && emp.complaints5d > 0 && (
                <span className="text-xs px-2.5 py-1 rounded-md bg-secondary text-muted-foreground">
                  Complaints (5d): {emp.complaints5d}
                </span>
              )}
            </div>
            {emp.narrative && emp.narrative.length > 0 && (
              <ul className="space-y-2">
                {emp.narrative.map((line, i) => (
                  <li key={`${line}-${i}`} className="text-sm text-muted-foreground pl-3 border-l-2 border-accent/40">
                    {line}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-6 rounded-2xl border border-border bg-card p-6">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Risk explainability</div>
          <div className="text-sm text-muted-foreground mb-4">
            Confidence {Math.round((emp.riskConfidence ?? 0) * 100)}% · {formatCalibrationBand(emp.riskCalibrationBand)}
          </div>
          {!emp.riskFactors || emp.riskFactors.length === 0 ? (
            <div className="text-sm text-muted-foreground">No factor-level signal available yet.</div>
          ) : (
            <ul className="space-y-2">
              {emp.riskFactors.slice(0, 3).map((factor) => (
                <li key={factor.name} className="rounded-xl bg-secondary/40 px-3 py-2 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{humanizeFactorName(factor.name)}</div>
                    <div className="text-xs text-muted-foreground truncate">{factor.description}</div>
                  </div>
                  <div className="text-xs text-muted-foreground whitespace-nowrap">
                    {Math.round(factor.contribution_pct)}% impact
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <div className="md:col-span-2 rounded-2xl border border-border bg-card p-6">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-5">Timeline</div>
            {timeline.length === 0 ? (
              <div className="text-sm text-muted-foreground">No timeline events yet.</div>
            ) : (
              <ol className="relative ml-3 border-l border-border space-y-5">
                {timeline.map((t, i) => (
                  <li key={`${t.date}-${i}`} className="pl-5 relative">
                    <span
                      className={`absolute -left-[5px] top-1.5 size-2.5 rounded-full ring-4 ring-card ${
                        t.tone === "danger"
                          ? "bg-danger"
                          : t.tone === "warning"
                            ? "bg-warning"
                            : t.tone === "positive"
                              ? "bg-emerald"
                              : "bg-accent"
                      }`}
                    />
                    <div className="text-sm">{t.text}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{t.date}</div>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-5">Tickets</div>
            {tickets.length === 0 && <div className="text-sm text-muted-foreground">No tickets yet.</div>}
            <ul className="space-y-3">
              {tickets.map((t) => (
                <li key={t.id} className="p-3 rounded-xl bg-secondary/40">
                  <div className="text-xs font-mono text-muted-foreground">{t.id}</div>
                  <div className="text-sm font-medium mt-1 line-clamp-2">{t.title}</div>
                  <div className="mt-2 flex gap-1.5">
                    <StatusPill status={t.status} />
                    <PriorityPill priority={t.priority} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <OffboardingClearanceCard userId={emp.id} />
      </div>

      <EditProfileDialog
        open={editOpen}
        initialName={emp.name}
        initialDesignation={emp.role || ""}
        onClose={() => setEditOpen(false)}
        onSaved={refreshProfile}
      />
    </AppLayout>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-display text-2xl tracking-tight mt-1">{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

function humanizeFactorName(name: string): string {
  return name.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatCalibrationBand(value?: string): string {
  if (!value) return "unknown confidence";
  return value.replaceAll("_", " ");
}

function deriveRiskLabel(score: number): "Low" | "Medium" | "High" {
  if (score >= 70) return "High";
  if (score >= 40) return "Medium";
  return "Low";
}

function formatTrendArrow(trend?: "up" | "down" | "stable"): string {
  if (trend === "up") return "↑";
  if (trend === "down") return "↓";
  return "→";
}

function formatTrendWord(trend?: "up" | "down" | "stable"): string {
  if (trend === "up") return "improving";
  if (trend === "down") return "declining";
  return "stable";
}
