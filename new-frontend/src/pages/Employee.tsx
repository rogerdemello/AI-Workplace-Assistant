import { AppLayout } from "@/components/layout/AppLayout";
import { useChat } from "@/contexts/ChatContext";
import { Clock, MessageSquare, Sparkles, ArrowRight, Activity, BellRing } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState } from "react";
import { CalendarConnectCard } from "@/components/employee/CalendarConnectCard";
import { WhatsappLinkCard } from "@/components/employee/WhatsappLinkCard";
import {
  cancelReminder,
  getPortalChats,
  getMyMoodTrend,
  getMyReminders,
  logMyMood,
  getPortalProfile,
  getPortalSummary,
  getPortalTimeline,
  type ChatPreview,
  type MoodTrend,
  type PortalProfile,
  type ReminderRow,
  type PortalSummary,
  type TimelineRow,
} from "@/lib/services";
import { LeaveRequestDialog } from "@/components/employee/LeaveRequestDialog";
import { MyLeaveRequests } from "@/components/employee/MyLeaveRequests";
import { toast } from "sonner";

function formatLastChat(iso: string | null | undefined): { value: string; hint: string } {
  if (!iso) return { value: "—", hint: "No chats yet" };
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 2) return { value: "Just now", hint: "Last message" };
    if (mins < 120) return { value: `${mins}m`, hint: "ago" };
    const hrs = Math.floor(mins / 60);
    if (hrs < 48) return { value: `${hrs}h`, hint: "ago" };
    return { value: d.toLocaleDateString(), hint: "Last activity" };
  } catch {
    return { value: "—", hint: "Last activity" };
  }
}

export default function Employee() {
  const { open, send } = useChat();
  const { session } = useAuth();
  const [summary, setSummary] = useState<PortalSummary | null>(null);
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [chats, setChats] = useState<ChatPreview[]>([]);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [reminders, setReminders] = useState<ReminderRow[]>([]);
  const [moodTrend, setMoodTrend] = useState<MoodTrend | null>(null);
  const [leaveNonce, setLeaveNonce] = useState(0);

  const greet = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 18) return "Good afternoon";
    return "Good evening";
  })();

  const askAndOpen = (msg: string) => {
    open();
    void send(msg);
  };

  const refreshSummary = () => {
    void getPortalSummary().then(setSummary);
  };

  const afterLeaveMutation = () => {
    refreshSummary();
    setLeaveNonce((n) => n + 1);
    void getPortalTimeline().then(setTimeline);
  };

  const loadReminders = () => {
    void getMyReminders().then(setReminders);
  };

  const loadMoodTrend = (userId: string) => {
    void getMyMoodTrend(userId).then(setMoodTrend);
  };

  const handleMoodLog = async (moodEmoji: "🙂" | "😐" | "😟" | "😔", moodScore: number) => {
    const ok = await logMyMood({ moodEmoji, moodScore });
    if (!ok) {
      toast.error("Unable to save mood right now.");
      return;
    }
    toast.success("Mood logged.");
    if (profile?.id) {
      loadMoodTrend(profile.id);
    }
  };

  const handleCancelReminder = async (reminderId: string) => {
    const ok = await cancelReminder(reminderId);
    if (!ok) {
      toast.error("Unable to cancel reminder.");
      return;
    }
    toast.success("Reminder cancelled.");
    loadReminders();
  };

  useEffect(() => {
    refreshSummary();
    getPortalProfile().then(setProfile);
    getPortalChats().then(setChats);
    getPortalTimeline().then(setTimeline);
    loadReminders();
  }, []);

  useEffect(() => {
    if (!profile?.id) return;
    loadMoodTrend(profile.id);
  }, [profile?.id]);

  const lastChat = formatLastChat(summary?.last_chat_at);

  return (
    <AppLayout title="My Day" subtitle="Your personal HR space">
      <div className="px-6 lg:px-10 py-8 max-w-6xl">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="text-sm text-muted-foreground">{greet}, {session?.name || profile?.name || "there"}</div>
          <h2 className="mt-2 font-display text-4xl leading-tight tracking-tight max-w-xl text-balance">
            {summary ? (
              <>
                You have <span className="text-accent">{summary.open_tickets}</span> open ticket
                {summary.open_tickets === 1 ? "" : "s"}.
              </>
            ) : (
              <>Welcome back.</>
            )}
          </h2>
          {profile?.department && (
            <p className="mt-2 text-sm text-muted-foreground">
              {profile.designation || "Team member"} · {profile.department}
            </p>
          )}
        </motion.div>

        <div className="mt-8 rounded-2xl bg-ink text-primary-foreground p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-aurora opacity-60" />
          <div className="relative flex flex-col md:flex-row items-start md:items-center gap-4">
            <div className="size-12 rounded-2xl bg-teal-grad grid place-items-center shadow-glow">
              <Sparkles className="size-5" />
            </div>
            <div className="flex-1">
              <div className="text-sm text-primary-foreground/70">MARK is here</div>
              <div className="font-display text-xl mt-0.5">What can I help with right now?</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {["Apply for leave", "Ask about a policy", "Talk to someone"].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => askAndOpen(p)}
                  className="text-sm px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                onClick={open}
                className="text-sm px-3 py-1.5 rounded-lg bg-accent text-accent-foreground font-medium flex items-center gap-1.5"
              >
                Open chat <ArrowRight className="size-3.5" />
              </button>
            </div>
          </div>
        </div>

        <div className="mt-10 grid md:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-border bg-card p-5 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-xs text-muted-foreground">Leave balance</div>
                <div className="mt-2 flex items-baseline gap-1.5">
                  <div className="font-display text-3xl tracking-tight">
                    {summary == null ? "—" : String(summary.leave_balance_remaining)}
                  </div>
                  <div className="text-sm text-muted-foreground">days left</div>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {summary == null
                    ? "Loading…"
                    : `${summary.used_leave_days_ytd} used YTD · ${summary.annual_leave_days} annual`}
                </div>
              </div>
              <LeaveRequestDialog onCreated={afterLeaveMutation} />
            </div>
          </div>
          <Stat
            label="Open tickets"
            value={summary === null ? "—" : String(summary.open_tickets)}
            unit=""
            hint={summary === null ? "Loading…" : `${summary.total_tickets} total`}
          />
          <Stat label="Last chat" value={lastChat.value} unit={lastChat.hint} hint={summary?.last_chat_at ? "From your conversations" : "Start a chat"} />
        </div>

        <div className="mt-10 max-w-xl">
          <MyLeaveRequests key={leaveNonce} onChanged={afterLeaveMutation} />
        </div>

        <div className="mt-10 rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center gap-2 mb-5">
            <Activity className="size-4 text-muted-foreground" />
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Recent activity</div>
          </div>
          {timeline.length === 0 ? (
            <p className="text-sm text-muted-foreground">No activity yet. Chats, tickets, surveys, and leave show up here.</p>
          ) : (
            <ol className="relative ml-3 border-l border-border space-y-4">
              {timeline.slice(0, 10).map((t, i) => (
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

        <div className="mt-10 grid md:grid-cols-3 gap-4">
          <div className="md:col-span-2 rounded-2xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Today</div>
                <div className="font-medium mt-1">Quick actions</div>
              </div>
              <Sparkles className="size-4 text-accent" />
            </div>
            <ul className="space-y-3">
              {[
                { title: "Submit a timesheet question", msg: "Help me with my timesheet" },
                { title: "Wellbeing check-in", msg: "I would like a wellbeing check-in" },
                { title: "Plan time off", msg: "Help me plan my upcoming leave" },
              ].map((s) => (
                <li key={s.title} className="flex items-center justify-between gap-4 p-3 rounded-xl hover:bg-secondary/60 transition-colors">
                  <div className="text-sm">{s.title}</div>
                  <button
                    type="button"
                    onClick={() => askAndOpen(s.msg)}
                    className="text-xs px-3 py-1.5 rounded-lg bg-ink text-primary-foreground hover:opacity-90 transition-opacity"
                  >
                    Ask MARK
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="flex items-center gap-2 mb-5">
              <Clock className="size-4 text-muted-foreground" />
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Pulse</div>
            </div>
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li>
                Mood trend:{" "}
                <span className="text-foreground font-medium capitalize">{moodTrend?.trend ?? "—"}</span>
              </li>
              <li>
                Mood score:{" "}
                <span className="text-foreground font-medium">
                  {moodTrend?.average_score == null ? "—" : `${Math.round(moodTrend.average_score)}/100`}
                </span>
              </li>
              <li>
                Active surveys:{" "}
                <span className="text-foreground font-medium">{summary?.active_surveys ?? "—"}</span>
              </li>
              <li>
                Your responses:{" "}
                <span className="text-foreground font-medium">{summary?.surveys_answered ?? "—"}</span>
              </li>
            </ul>
            <div className="mt-5">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-2">Quick mood check-in</div>
              <div className="flex flex-wrap gap-2">
                {[
                  { emoji: "🙂" as const, score: 85, label: "Good" },
                  { emoji: "😐" as const, score: 60, label: "Okay" },
                  { emoji: "😟" as const, score: 40, label: "Low" },
                  { emoji: "😔" as const, score: 20, label: "Stressed" },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => void handleMoodLog(item.emoji, item.score)}
                    className="text-xs px-2.5 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 transition-colors"
                  >
                    {item.emoji} {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <BellRing className="size-4 text-muted-foreground" />
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">My reminders</div>
            </div>
            <button type="button" onClick={loadReminders} className="text-xs text-accent hover:underline">
              Refresh
            </button>
          </div>
          {reminders.length === 0 ? (
            <p className="text-sm text-muted-foreground">No active reminders yet. You can ask MARK to set one.</p>
          ) : (
            <ul className="space-y-3">
              {reminders.slice(0, 6).map((row) => (
                <li key={row.id} className="rounded-xl border border-border p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{row.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{row.message}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      Next: {formatReminderDate(row.next_trigger_at)} · {row.schedule_kind.replace("_", " ")}
                    </div>
                  </div>
                  {row.status === "active" && (
                    <button
                      type="button"
                      onClick={() => void handleCancelReminder(row.id)}
                      className="shrink-0 text-xs px-2.5 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <WhatsappLinkCard />

        <CalendarConnectCard />

        <div className="mt-10 rounded-2xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <MessageSquare className="size-4 text-muted-foreground" />
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Recent conversations</div>
            </div>
            <button type="button" onClick={open} className="text-xs text-accent hover:underline">
              Open chat →
            </button>
          </div>
          <ul className="divide-y divide-border">
            {chats.length === 0 && <li className="py-3 text-sm text-muted-foreground">No recent conversations yet.</li>}
            {chats.map((c) => (
              <li key={c.id} className="py-3 first:pt-0 last:pb-0 flex items-start gap-3">
                <div className="size-8 rounded-full bg-secondary grid place-items-center">
                  <MessageSquare className="size-3.5 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{c.title}</div>
                  <div className="text-xs text-muted-foreground truncate">{c.preview}</div>
                </div>
                <div className="text-[11px] text-muted-foreground shrink-0">{c.when}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </AppLayout>
  );
}

function Stat({ label, value, unit, hint }: { label: string; value: string; unit?: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <div className="font-display text-3xl tracking-tight">{value}</div>
        {unit && <div className="text-sm text-muted-foreground">{unit}</div>}
      </div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

function formatReminderDate(value: string | null): string {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Not scheduled";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
