import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { Activity, AlertTriangle, ArrowUpRight, Brain, GitBranch, MessageSquare, Sparkles, Tags, User, X } from "lucide-react";
import { toast } from "sonner";
import { PriorityPill, StatusPill } from "@/components/ui-bits";
import { cn } from "@/lib/utils";
import type { Ticket } from "@/lib/domain-types";
import type { TicketDetailView } from "@/components/tickets/ticket-insights";
import {
  addInternalTicketNote,
  addTicketMessage,
  assignTicket,
  closeTicket,
  escalateTicket,
  getRelatedTickets,
  getTicketActionLogs,
  getTicketAiSummary,
  getTicketMessages,
  getTicketSentimentHistory,
  listTicketAssignees,
  markTicketInProgress,
  scheduleTicketCheckin,
  type TicketActionLog,
  type TicketAiSummary,
  type TicketAssignee,
  type TicketMessage,
  type TicketSentimentHistory,
} from "@/lib/services";
import { Line, LineChart, ResponsiveContainer, Tooltip as RechartsTooltip } from "recharts";

export function TicketDecisionPanel({
  selected,
  setSelected,
  nameByUserId,
  raisedByLabel,
  onTicketUpdated,
}: {
  selected: TicketDetailView | null;
  setSelected: (value: TicketDetailView | null) => void;
  nameByUserId: Record<string, string>;
  raisedByLabel: (id: string) => string;
  onTicketUpdated: (ticketId: string) => void;
}) {
  const [assignees, setAssignees] = useState<TicketAssignee[]>([]);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [actionLogs, setActionLogs] = useState<TicketActionLog[]>([]);
  const [replyText, setReplyText] = useState("");
  const [internalNoteText, setInternalNoteText] = useState("");
  const [reassignTo, setReassignTo] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [threadFilter, setThreadFilter] = useState<"all" | "employee" | "internal">("all");
  const [relatedTickets, setRelatedTickets] = useState<Ticket[]>([]);
  const [aiSummary, setAiSummary] = useState<TicketAiSummary | null>(null);
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false);
  const [sentimentHistory, setSentimentHistory] = useState<TicketSentimentHistory | null>(null);
  // Drives the live SLA countdown — re-render every 30s while the drawer is open.
  const [, setNowTick] = useState(0);

  useEffect(() => {
    if (!selected) return;
    setReplyText("");
    setInternalNoteText("");
    setReassignTo("");
    setThreadFilter("all");
    setRelatedTickets([]);
    setAiSummary(null);
    setSentimentHistory(null);
    setAiSummaryLoading(true);
    getTicketMessages(selected.id).then(setMessages);
    getTicketActionLogs(selected.id).then(setActionLogs);
    listTicketAssignees().then(setAssignees);
    getTicketAiSummary(selected.id)
      .then((s) => setAiSummary(s))
      .finally(() => setAiSummaryLoading(false));
    getTicketSentimentHistory(selected.id).then(setSentimentHistory);
    // Auto-load related tickets when the drawer opens — feature uses them as
    // a duplicate-detection signal, so users shouldn't have to hunt for the
    // button before they see related issues.
    void getRelatedTickets(selected.id).then((rows) => {
      setRelatedTickets(rows.filter((row) => row.id !== selected.id));
    });
  }, [selected?.id]);

  // Tick once a minute so the SLA countdown stays approximately fresh without
  // re-rendering on every animation frame.
  useEffect(() => {
    if (!selected) return undefined;
    const interval = window.setInterval(() => setNowTick((n) => n + 1), 30_000);
    return () => window.clearInterval(interval);
  }, [selected?.id]);

  const refreshAiSummary = async () => {
    if (!selected) return;
    setAiSummaryLoading(true);
    const next = await getTicketAiSummary(selected.id, true);
    setAiSummary(next);
    setAiSummaryLoading(false);
  };

  const timelineItems = useMemo(() => {
    if (!selected) return [];
    if (!actionLogs.length) return selected.timeline;
    return actionLogs.map((log) => {
      const label = log.action_type.replaceAll("_", " ");
      if (log.details?.trim()) return `${label}: ${log.details}`;
      return label;
    });
  }, [actionLogs, selected]);

  const thread = useMemo(() => {
    if (!selected) return [];
    if (!messages.length) return selected.thread;
    return messages.map((m) => ({
      by: m.is_internal ? ("mark" as const) : m.sender_id ? ("mark" as const) : ("employee" as const),
      text: m.is_internal ? `[Internal note] ${m.message_text}` : m.message_text,
    }));
  }, [messages, selected]);

  const filteredThread = useMemo(() => {
    if (threadFilter === "all") return thread;
    if (threadFilter === "internal") return thread.filter((m) => m.text.startsWith("[Internal note]"));
    return thread.filter((m) => !m.text.startsWith("[Internal note]"));
  }, [thread, threadFilter]);

  const runReplyWorkflow = async () => {
    if (!selected || !replyText.trim()) return;
    setBusy("reply");
    const saved = await addTicketMessage(selected.id, replyText.trim());
    if (!saved) {
      setBusy(null);
      toast.error("Could not add ticket reply.");
      return;
    }
    await markTicketInProgress(selected.id);
    const refreshedMessages = await getTicketMessages(selected.id);
    const refreshedActions = await getTicketActionLogs(selected.id);
    setMessages(refreshedMessages);
    setActionLogs(refreshedActions);
    setReplyText("");
    setBusy(null);
    toast.success("Reply logged and ticket moved to In progress.");
    onTicketUpdated(selected.id);
  };

  const runReassignWorkflow = async () => {
    if (!selected || !reassignTo) return;
    setBusy("reassign");
    const updated = await assignTicket(selected.id, reassignTo);
    setBusy(null);
    if (!updated) {
      toast.error("Could not reassign ticket.");
      return;
    }
    setSelected({ ...selected, assignedTo: updated.assignedTo, status: updated.status, updatedAt: updated.updatedAt });
    const refreshedActions = await getTicketActionLogs(selected.id);
    setActionLogs(refreshedActions);
    toast.success("Ticket reassigned.");
    onTicketUpdated(selected.id);
  };

  const runEscalateWorkflow = async () => {
    if (!selected) return;
    setBusy("escalate");
    const updated = await escalateTicket(selected.id, "Escalated from HR decision panel");
    setBusy(null);
    if (!updated) {
      toast.error("Could not escalate ticket.");
      return;
    }
    setSelected({ ...selected, status: updated.status, priority: updated.priority, updatedAt: updated.updatedAt, slaRemainingHours: updated.slaRemainingHours });
    const refreshedActions = await getTicketActionLogs(selected.id);
    setActionLogs(refreshedActions);
    toast.success("Ticket escalated.");
    onTicketUpdated(selected.id);
  };

  const runScheduleWorkflow = async () => {
    if (!selected) return;
    setBusy("checkin");
    const ok = await scheduleTicketCheckin(selected.id, "Scheduled from HR decision panel");
    setBusy(null);
    if (!ok) {
      toast.error("Could not schedule check-in.");
      return;
    }
    const refreshedMessages = await getTicketMessages(selected.id);
    const refreshedActions = await getTicketActionLogs(selected.id);
    setMessages(refreshedMessages);
    setActionLogs(refreshedActions);
    toast.success("Check-in scheduled and linked to ticket.");
    onTicketUpdated(selected.id);
  };

  const runInternalNoteWorkflow = async () => {
    if (!selected || !internalNoteText.trim()) return;
    setBusy("internal-note");
    const saved = await addInternalTicketNote(selected.id, internalNoteText.trim());
    setBusy(null);
    if (!saved) {
      toast.error("Could not add internal note.");
      return;
    }
    const refreshedMessages = await getTicketMessages(selected.id);
    const refreshedActions = await getTicketActionLogs(selected.id);
    setMessages(refreshedMessages);
    setActionLogs(refreshedActions);
    setInternalNoteText("");
    toast.success("Internal note added.");
    onTicketUpdated(selected.id);
  };

  const runCloseWorkflow = async () => {
    if (!selected) return;
    setBusy("close");
    const updated = await closeTicket(selected.id, "Closed from HR decision panel.");
    setBusy(null);
    if (!updated) {
      toast.error("Could not close ticket.");
      return;
    }
    setSelected({ ...selected, status: updated.status, updatedAt: updated.updatedAt, slaRemainingHours: updated.slaRemainingHours });
    const refreshedActions = await getTicketActionLogs(selected.id);
    setActionLogs(refreshedActions);
    toast.success("Ticket closed.");
    onTicketUpdated(selected.id);
  };

  return (
    <AnimatePresence>
      {selected && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm" onClick={() => setSelected(null)} />
          <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 32 }} className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-card border-l border-border shadow-elevated overflow-y-auto scrollbar-thin">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="text-xs font-mono text-muted-foreground">{selected.id}</div>
                <button onClick={() => setSelected(null)} className="size-8 rounded-lg hover:bg-secondary grid place-items-center"><X className="size-4" /></button>
              </div>
              <h3 className="font-display text-2xl tracking-tight">{selected.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{selected.summary}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <StatusPill status={selected.status} />
                <PriorityPill priority={selected.priority} />
              </div>

              <Section icon={Brain} title="AI summary">
                <div className="text-sm">
                  {aiSummaryLoading && !aiSummary ? (
                    <span className="text-muted-foreground">Generating summary…</span>
                  ) : (
                    aiSummary?.summary || selected.aiInsight
                  )}
                </div>
                <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                  {aiSummary && (
                    <>
                      <span>
                        {aiSummary.model === "azure-openai" ? "LLM" : "Template"} · over{" "}
                        {aiSummary.message_count} message{aiSummary.message_count === 1 ? "" : "s"}
                      </span>
                      <button
                        type="button"
                        onClick={() => void refreshAiSummary()}
                        disabled={aiSummaryLoading}
                        className="underline hover:text-foreground disabled:opacity-50"
                      >
                        {aiSummaryLoading ? "Refreshing…" : "Refresh"}
                      </button>
                    </>
                  )}
                </div>
              </Section>

              <SlaCountdown
                slaHours={selected.slaHours}
                slaRemainingHours={selected.slaRemainingHours}
                slaAction={selected.slaAction}
              />

              <Section icon={User} title="Employee Snapshot">
                <div className="grid grid-cols-2 gap-3 mt-1 text-xs">
                  <Metric label="Sentiment" value={selected.employeeSnapshot.sentimentLabel} />
                  <Metric label="Risk Level" value={selected.employeeSnapshot.riskLabel} />
                  <Metric label="Last Active" value={selected.employeeSnapshot.lastActive} />
                  <Metric label="Open Tickets" value={String(selected.employeeSnapshot.openTickets)} />
                </div>
              </Section>

              <Section icon={Sparkles} title="Suggested actions">
                <div className="flex flex-wrap gap-2">
                  <ActionChip
                    label="Escalate"
                    tone="danger"
                    busy={busy === "escalate"}
                    disabled={busy !== null}
                    onClick={() => void runEscalateWorkflow()}
                  />
                  <ActionChip
                    label="Schedule 1:1"
                    tone="neutral"
                    busy={busy === "checkin"}
                    disabled={busy !== null}
                    onClick={() => void runScheduleWorkflow()}
                  />
                  <ActionChip
                    label="Loop in manager"
                    tone="neutral"
                    busy={busy === "internal-note"}
                    disabled={busy !== null}
                    onClick={() => {
                      const note =
                        "Looping in manager for awareness — please review this thread and coordinate next steps.";
                      setInternalNoteText(note);
                    }}
                  />
                  <ActionChip
                    label={selected.status === "resolved" ? "Reopen later" : "Close ticket"}
                    tone="emerald"
                    busy={busy === "close"}
                    disabled={busy !== null || selected.status === "resolved"}
                    onClick={() => void runCloseWorkflow()}
                  />
                </div>
                {selected.suggestedActions.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {selected.suggestedActions.map((action) => (
                      <li key={action} className="flex items-start gap-1.5">
                        <ArrowUpRight className="size-3 mt-0.5 text-accent shrink-0" />
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section icon={Activity} title="Sentiment trajectory">
                <SentimentSparkline history={sentimentHistory} />
              </Section>

              <div className="mt-6 space-y-4">
                <Field label="Category" value={selected.category} />
                <Field label="Raised by" value={raisedByLabel(selected.raisedBy || "")} />
                <Field label="Assigned to" value={selected.assignedTo ? (nameByUserId[selected.assignedTo] || selected.assignedTo) : "Priya Sharma (HR Business Partner)"} />
                <Field label="Priority reason" value={`${selected.priority} (${selected.priorityReason})`} />
                <Field label="Created" value={selected.createdAt} />
                <Field label="Updated" value={selected.updatedAt} />
              </div>

              <Section icon={Tags} title="Tags">
                <div className="flex flex-wrap gap-2">
                  {selected.tags.map((tag) => (
                    <span key={tag} className="text-xs px-2 py-1 rounded-md bg-card border border-border">{tag}</span>
                  ))}
                </div>
              </Section>

              {relatedTickets.length > 0 && (
                <div className="mt-4 p-3 rounded-xl bg-warning-soft text-warning text-sm flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5">
                    <GitBranch className="size-4" /> {relatedTickets.length} possibly related ticket
                    {relatedTickets.length === 1 ? "" : "s"} detected
                  </span>
                </div>
              )}
              {relatedTickets.length > 0 && (
                <Section icon={GitBranch} title="Possibly related tickets">
                  <ul className="space-y-2">
                    {relatedTickets.map((row) => (
                      <li key={row.id} className="text-xs rounded-md border border-border p-2">
                        <div className="font-medium">{row.id}</div>
                        <div className="text-muted-foreground mt-1 line-clamp-2">{row.query}</div>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              <Section icon={Activity} title="Timeline">
                <ul className="space-y-2 text-sm">{timelineItems.map((item, idx) => <li key={`${item}-${idx}`}>• {item}</li>)}</ul>
              </Section>

              <Section icon={MessageSquare} title="Conversation Thread">
                <div className="mb-3 flex items-center gap-2">
                  <FilterPill active={threadFilter === "all"} onClick={() => setThreadFilter("all")} label="All" />
                  <FilterPill active={threadFilter === "employee"} onClick={() => setThreadFilter("employee")} label="Employee-visible" />
                  <FilterPill active={threadFilter === "internal"} onClick={() => setThreadFilter("internal")} label="Internal" />
                </div>
                <div className="space-y-2 text-sm">
                  {filteredThread.map((m, i) => (
                    <div key={`${m.by}-${i}`} className="p-2 rounded-md bg-card border border-border">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-[11px] uppercase text-muted-foreground">{m.by === "employee" ? "Employee" : "Mark"}</div>
                        <span
                          className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded-md border",
                            m.text.startsWith("[Internal note]")
                              ? "bg-warning-soft text-warning border-warning/40"
                              : "bg-emerald-soft text-emerald border-emerald/40",
                          )}
                        >
                          {m.text.startsWith("[Internal note]") ? "Internal" : "Employee-visible"}
                        </span>
                      </div>
                      <div className="mt-1">{m.text}</div>
                    </div>
                  ))}
                  {filteredThread.length === 0 && (
                    <div className="text-xs text-muted-foreground p-2 rounded-md border border-dashed border-border">
                      No messages in this view.
                    </div>
                  )}
                </div>
              </Section>

              <div className="mt-6 rounded-xl border border-border bg-secondary/20 p-4 space-y-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Workflow Actions</div>
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  rows={3}
                  placeholder="Reply via MARK (employee-visible message)"
                  className="w-full rounded-lg border border-border bg-card p-2.5 text-sm outline-none"
                />
                <button
                  className="h-10 w-full rounded-lg bg-ink text-primary-foreground text-sm font-medium disabled:opacity-60"
                  onClick={() => void runReplyWorkflow()}
                  disabled={busy !== null || !replyText.trim()}
                >
                  {busy === "reply" ? "Sending…" : "Reply via MARK"}
                </button>

                <textarea
                  value={internalNoteText}
                  onChange={(e) => setInternalNoteText(e.target.value)}
                  rows={2}
                  placeholder="HR internal note (private)"
                  className="w-full rounded-lg border border-border bg-card p-2.5 text-sm outline-none"
                />
                <button
                  className="h-10 w-full rounded-lg border border-border bg-card text-sm font-medium disabled:opacity-60"
                  onClick={() => void runInternalNoteWorkflow()}
                  disabled={busy !== null || !internalNoteText.trim()}
                >
                  {busy === "internal-note" ? "Saving note…" : "Save Internal Note"}
                </button>

                <div className="grid grid-cols-[1fr_auto] gap-2">
                  <select
                    value={reassignTo}
                    onChange={(e) => setReassignTo(e.target.value)}
                    className="h-10 rounded-lg border border-border bg-card px-2.5 text-sm"
                  >
                    <option value="">Select assignee</option>
                    {assignees.map((a) => (
                      <option key={a.id} value={a.id}>{a.name} ({a.role})</option>
                    ))}
                  </select>
                  <button
                    className="h-10 px-4 rounded-lg bg-secondary text-sm disabled:opacity-60"
                    onClick={() => void runReassignWorkflow()}
                    disabled={busy !== null || !reassignTo}
                  >
                    {busy === "reassign" ? "Reassigning…" : "Reassign"}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    className="h-10 px-4 rounded-lg bg-danger-soft text-danger text-sm disabled:opacity-60"
                    onClick={() => void runEscalateWorkflow()}
                    disabled={busy !== null}
                  >
                    {busy === "escalate" ? "Escalating…" : "Escalate"}
                  </button>
                  <button
                    className="h-10 px-4 rounded-lg bg-secondary text-sm disabled:opacity-60"
                    onClick={() => void runScheduleWorkflow()}
                    disabled={busy !== null}
                  >
                    {busy === "checkin" ? "Scheduling…" : "Schedule Check-in"}
                  </button>
                </div>
                <button
                  className="h-10 w-full rounded-lg bg-emerald-soft text-emerald text-sm font-medium disabled:opacity-60"
                  onClick={() => void runCloseWorkflow()}
                  disabled={busy !== null || selected.status === "resolved"}
                >
                  {busy === "close" ? "Closing…" : selected.status === "resolved" ? "Ticket Closed" : "Close Ticket"}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function Section({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode }) {
  return (
    <div className="mt-6 p-4 rounded-xl border border-border bg-secondary/20">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        <Icon className="size-3.5" />
        {title}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground capitalize">{label}</span><span className={cn("font-medium capitalize", label === "Priority reason" && "text-right max-w-[60%]")}>{value}</span></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-card px-2.5 py-2"><div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div><div className="text-sm font-medium mt-1">{value}</div></div>;
}

function FilterPill({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "text-[11px] px-2 py-1 rounded-md border transition-colors",
        active ? "bg-card border-border text-foreground" : "bg-transparent border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

function ActionChip({
  label,
  tone,
  busy,
  disabled,
  onClick,
}: {
  label: string;
  tone: "danger" | "neutral" | "emerald";
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  const toneCls =
    tone === "danger"
      ? "bg-danger-soft text-danger border-danger/30 hover:bg-danger-soft/80"
      : tone === "emerald"
        ? "bg-emerald-soft text-emerald border-emerald/30 hover:bg-emerald-soft/80"
        : "bg-card text-foreground border-border hover:bg-secondary";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "text-xs px-3 py-1.5 rounded-md border font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        toneCls,
      )}
    >
      {busy ? "Working…" : label}
    </button>
  );
}

function SlaCountdown({
  slaHours,
  slaRemainingHours,
  slaAction,
}: {
  slaHours: number;
  slaRemainingHours: number;
  slaAction: string | null;
}) {
  const [mountedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  const elapsedHours = (now - mountedAt) / 3_600_000;
  const liveRemaining = slaRemainingHours - elapsedHours;
  const pct = Math.max(0, Math.min(100, (liveRemaining / slaHours) * 100));
  const breached = liveRemaining <= 0;
  const danger = breached || pct < 25;
  const warn = !danger && pct < 50;

  return (
    <div
      className={cn(
        "mt-5 p-3 rounded-xl text-sm border",
        danger
          ? "bg-danger-soft text-danger border-danger/40"
          : warn
            ? "bg-warning-soft text-warning border-warning/40"
            : "bg-secondary/40 text-foreground border-border",
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="size-4 mt-0.5 shrink-0" />
        <div className="flex-1">
          <div className="font-medium">
            {breached ? "SLA breached" : `SLA: ${formatHours(liveRemaining)} remaining`}
          </div>
          <div className="text-xs mt-0.5 opacity-90">
            {danger && slaAction ? slaAction : `Window: ${slaHours}h total`}
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-card/60 overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                danger ? "bg-danger" : warn ? "bg-warning" : "bg-emerald",
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function formatHours(hours: number): string {
  if (hours <= 0) return "0h";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m`;
  const whole = Math.floor(hours);
  const minutes = Math.round((hours - whole) * 60);
  if (minutes === 0) return `${whole}h`;
  return `${whole}h ${minutes}m`;
}

function SentimentSparkline({ history }: { history: TicketSentimentHistory | null }) {
  if (!history) {
    return <div className="text-xs text-muted-foreground">Loading sentiment trajectory…</div>;
  }
  const points = history.points.filter((p) => p.score != null);
  if (points.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No sentiment signals since this ticket opened.
      </div>
    );
  }
  const latest = points[points.length - 1];
  const first = points[0];
  const delta = (latest.score ?? 0) - (first.score ?? 0);
  const deltaTone = delta > 5 ? "text-emerald" : delta < -5 ? "text-danger" : "text-muted-foreground";
  return (
    <div>
      <div className="h-16">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <Line
              type="monotone"
              dataKey="score"
              stroke="hsl(var(--accent))"
              strokeWidth={2}
              dot={false}
            />
            <RechartsTooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 11,
              }}
              formatter={(v: number) => [`${v}`, "Score"]}
              labelFormatter={(label) => String(label)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">
          {points.length} day{points.length === 1 ? "" : "s"} of data since ticket opened
        </span>
        <span className={deltaTone}>
          {delta > 0 ? "+" : ""}
          {Math.round(delta)} since ticket open
        </span>
      </div>
    </div>
  );
}
