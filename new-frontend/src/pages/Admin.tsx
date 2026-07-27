import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Avatar } from "@/components/ui-bits";
import { Shield, Plus, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  createAutomationRule,
  getAdminUsers,
  getManagerEffectiveness,
  getProactiveSuppressionPolicy,
  listAutomationRules,
  updateAutomationRule,
  updateProactiveSuppressionPolicy,
  listIntegrationProviders,
  triggerHrmsSync,
  triggerPayrollSync,
  getWellbeingHighRisk,
  getWeeklyWellbeingSummary,
  inviteUser,
  adminUpdateUser,
  type AdminUserRow,
  type AutomationRuleRow,
  type HighRiskEmployeeRow,
  type IntegrationProviderItem,
  type ManagerEffectivenessRow,
  type ProactiveSuppressionPolicy,
  type WeeklyWellbeingSummary,
} from "@/lib/services";
import { toast } from "sonner";

const ROLE_OPTIONS = ["employee", "manager", "hr", "admin"] as const;

const roleColors: Record<string, string> = {
  admin: "bg-danger-soft text-danger",
  hr: "bg-accent-soft text-accent",
  employee: "bg-secondary text-foreground",
};

export default function Admin() {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [managerEffectiveness, setManagerEffectiveness] = useState<ManagerEffectivenessRow[]>([]);
  const [automationRules, setAutomationRules] = useState<AutomationRuleRow[]>([]);
  const [proactivePolicy, setProactivePolicy] = useState<ProactiveSuppressionPolicy | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationProviderItem[]>([]);
  const [syncBusyKey, setSyncBusyKey] = useState<string | null>(null);
  const [highRiskRows, setHighRiskRows] = useState<HighRiskEmployeeRow[]>([]);
  const [weeklySummary, setWeeklySummary] = useState<WeeklyWellbeingSummary | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [actionBusyId, setActionBusyId] = useState<string | null>(null);

  const refreshUsers = () => getAdminUsers().then(setUsers);

  const changeUserRole = async (user: AdminUserRow, role: string) => {
    setOpenMenuId(null);
    if (role === user.role) return;
    setActionBusyId(user.id);
    const ok = await adminUpdateUser(user.id, { role });
    setActionBusyId(null);
    if (!ok) {
      toast.error(`Could not change role for ${user.name}.`);
      return;
    }
    toast.success(`${user.name} is now ${role}.`);
    void refreshUsers();
  };

  const toggleUserActive = async (user: AdminUserRow) => {
    setOpenMenuId(null);
    setActionBusyId(user.id);
    const nextStatus = user.active ? "inactive" : "active";
    const ok = await adminUpdateUser(user.id, { status: nextStatus });
    setActionBusyId(null);
    if (!ok) {
      toast.error(`Could not update ${user.name}.`);
      return;
    }
    toast.success(`${user.name} ${user.active ? "deactivated" : "reactivated"}.`);
    void refreshUsers();
  };

  useEffect(() => {
    getAdminUsers().then(setUsers);
    getManagerEffectiveness(12).then(setManagerEffectiveness);
    listAutomationRules().then(setAutomationRules);
    getProactiveSuppressionPolicy().then(setProactivePolicy);
    listIntegrationProviders().then(setIntegrations);
    getWellbeingHighRisk(8).then(setHighRiskRows);
    getWeeklyWellbeingSummary().then(setWeeklySummary);
  }, []);

  const createDefaultEscalationRule = async () => {
    const created = await createAutomationRule({
      name: "Auto-escalate complaint tickets",
      eventType: "ticket_created",
      conditions: { category_in: ["complaint"] },
      actions: { auto_escalate: true, set_priority: "critical" },
    });
    if (!created) {
      toast.error("Could not create automation rule.");
      return;
    }
    toast.success("Automation rule created.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const createStatusRule = async () => {
    const created = await createAutomationRule({
      name: "Mark in-progress tickets as high priority",
      eventType: "ticket_updated",
      conditions: { to_status_in: ["in_progress"] },
      actions: { set_priority: "high" },
    });
    if (!created) {
      toast.error("Could not create automation rule.");
      return;
    }
    toast.success("Ticket update automation added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const createLeaveReviewRule = async () => {
    const created = await createAutomationRule({
      name: "Leave reviewed follow-up note",
      eventType: "leave_reviewed",
      conditions: { leave_status_in: ["approved", "rejected"] },
      actions: {
        set_review_comment_template: "Automated follow-up: leave request is {status}.",
        notify_hr: true,
        notification_title: "Leave review automation applied",
      },
    });
    if (!created) {
      toast.error("Could not create automation rule.");
      return;
    }
    toast.success("Leave review automation added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const createWellbeingAlertRule = async () => {
    const created = await createAutomationRule({
      name: "Alert HR on risky check-ins",
      eventType: "daily_checkin_recorded",
      conditions: { signal_triage_in: ["high", "watch"], mood_in: ["stressed", "low"] },
      actions: {
        create_hr_notification: true,
        notification_title: "Wellbeing check-in needs review",
        notification_body_template: "Employee {user_id} check-in mood={mood}, triage={triage_level}.",
        notification_severity: "warning",
        notification_type: "wellbeing_automation",
      },
    });
    if (!created) {
      toast.error("Could not create wellbeing alert rule.");
      return;
    }
    toast.success("Wellbeing automation added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const createTicketCloseFollowupRule = async () => {
    const created = await createAutomationRule({
      name: "Notify HR on ticket closure",
      eventType: "ticket_closed",
      conditions: {},
      actions: {
        create_hr_notification: true,
        notification_title: "Ticket closed workflow",
        notification_body_template: "Ticket {ticket_id} closed. Review for post-resolution follow-up.",
        notification_type: "ticket_closed_workflow",
        notification_severity: "info",
      },
    });
    if (!created) {
      toast.error("Could not create ticket close workflow rule.");
      return;
    }
    toast.success("Ticket close workflow rule added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const createInternalNoteEscalationRule = async () => {
    const created = await createAutomationRule({
      name: "Escalate severe complaint internal notes",
      eventType: "ticket_internal_note_added",
      conditions: { category_in: ["complaint"], priority_in: ["high", "critical"] },
      actions: {
        create_hr_notification: true,
        notification_title: "Internal note requires review",
        notification_body_template: "Complaint ticket {ticket_id} has a new internal note. Please review.",
        notification_type: "ticket_internal_note_workflow",
        notification_severity: "warning",
      },
    });
    if (!created) {
      toast.error("Could not create internal note automation.");
      return;
    }
    toast.success("Internal note workflow rule added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  const toggleRule = async (rule: AutomationRuleRow) => {
    const updated = await updateAutomationRule(rule.id, { enabled: !rule.enabled });
    if (!updated) {
      toast.error("Could not update rule.");
      return;
    }
    setAutomationRules((prev) => prev.map((item) => (item.id === rule.id ? updated : item)));
  };

  const saveProactivePolicy = async () => {
    if (!proactivePolicy) return;
    const updated = await updateProactiveSuppressionPolicy(proactivePolicy);
    if (!updated) {
      toast.error("Could not update suppression policy.");
      return;
    }
    setProactivePolicy(updated);
    toast.success("Suppression policy updated.");
  };

  const runIntegrationSync = async (provider: IntegrationProviderItem) => {
    setSyncBusyKey(provider.key);
    const result =
      provider.category === "hrms"
        ? await triggerHrmsSync(provider.key, true)
        : provider.category === "payroll"
          ? await triggerPayrollSync(provider.key, true)
          : null;
    setSyncBusyKey(null);
    if (!result) {
      toast.error(`Could not run ${provider.key} sync.`);
      return;
    }
    toast.success(`${provider.key}: ${result.details}`);
  };

  const createLeaveRequestedRule = async () => {
    const created = await createAutomationRule({
      name: "Notify HR on leave requests",
      eventType: "leave_requested",
      conditions: {},
      actions: {
        create_hr_notification: true,
        notification_title: "New leave request submitted",
        notification_body_template: "Leave {leave_id} was requested and is pending review.",
        notification_type: "leave_requested_workflow",
        notification_severity: "info",
      },
    });
    if (!created) {
      toast.error("Could not create leave requested workflow rule.");
      return;
    }
    toast.success("Leave requested workflow rule added.");
    setAutomationRules((prev) => [created, ...prev]);
  };

  return (
    <AppLayout
      title="Admin"
      subtitle="Roles, permissions, and access"
      topbarAction={
        <button
          type="button"
          onClick={() => setInviteOpen(true)}
          className="hidden md:inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-ink text-primary-foreground text-sm"
        >
          <Plus className="size-4" /> Invite
        </button>
      }
    >
      <div className="px-6 lg:px-10 py-8 max-w-6xl">
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <Stat label="Total users" value={String(users.length)} />
          <Stat label="HR seats" value={String(users.filter((u) => u.role === "hr").length)} hint="Live directory" />
          <Stat label="Employees" value={String(users.filter((u) => u.role === "employee").length)} hint="Active accounts" />
        </div>

        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="grid grid-cols-[1fr_140px_120px_100px_40px] px-5 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground border-b border-border">
            <div>User</div>
            <div>Role</div>
            <div>Department</div>
            <div>Status</div>
            <div />
          </div>
          <ul className="divide-y divide-border">
            {users.map((u) => (
              <li
                key={u.id}
                className="grid grid-cols-[1fr_140px_120px_100px_40px] gap-3 items-center px-5 py-3 hover:bg-secondary/40 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Avatar initials={u.initials} size="sm" />
                  <div className="min-w-0">
                    <div className="text-sm truncate">{u.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                  </div>
                </div>
                <div>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium capitalize",
                      roleColors[u.role] || "bg-secondary text-foreground",
                    )}
                  >
                    {u.role === "admin" && <Shield className="size-3" />}
                    {u.role}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground truncate">{u.department}</div>
                <div className="flex items-center gap-1.5 text-xs">
                  <span className={cn("size-1.5 rounded-full", u.active ? "bg-emerald" : "bg-muted-foreground/40")} />
                  {u.active ? "Active" : "Inactive"}
                </div>
                <div className="relative justify-self-end">
                  <button
                    type="button"
                    disabled={actionBusyId === u.id}
                    onClick={() => setOpenMenuId((prev) => (prev === u.id ? null : u.id))}
                    className="size-7 rounded-md hover:bg-secondary grid place-items-center disabled:opacity-50"
                  >
                    <MoreHorizontal className="size-4 text-muted-foreground" />
                  </button>
                  {openMenuId === u.id && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setOpenMenuId(null)} />
                      <div className="absolute right-0 mt-1 z-20 w-44 rounded-lg border border-border bg-card shadow-lg py-1 text-sm">
                        <div className="px-3 py-1.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Set role</div>
                        {ROLE_OPTIONS.map((role) => (
                          <button
                            key={role}
                            type="button"
                            onClick={() => void changeUserRole(u, role)}
                            className={cn(
                              "w-full text-left px-3 py-1.5 hover:bg-secondary capitalize flex items-center justify-between",
                              u.role === role && "text-accent",
                            )}
                          >
                            {role}
                            {u.role === role && <span className="text-xs">current</span>}
                          </button>
                        ))}
                        <div className="my-1 h-px bg-border" />
                        <button
                          type="button"
                          onClick={() => void toggleUserActive(u)}
                          className="w-full text-left px-3 py-1.5 hover:bg-secondary text-danger"
                        >
                          {u.active ? "Deactivate user" : "Reactivate user"}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </li>
            ))}
            {users.length === 0 && (
              <li className="px-5 py-6 text-sm text-muted-foreground">No users returned — check HR authentication and API availability.</li>
            )}
          </ul>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Manager effectiveness</div>
            <div className="text-sm mt-1">Team health leadership signal</div>
          </div>
          <ul className="divide-y divide-border">
            {managerEffectiveness.map((row) => (
              <li key={row.manager_id} className="px-5 py-3 grid grid-cols-[1fr_120px_120px_120px_120px] gap-3 items-center">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{row.manager_name}</div>
                  <div className="text-xs text-muted-foreground">Team size: {row.team_size}</div>
                </div>
                <div className="text-xs text-muted-foreground">
                  Sentiment {Math.round(row.avg_sentiment_score)}% · {sentimentTrendLabel(row.avg_sentiment_score)}
                </div>
                <div className="text-xs text-muted-foreground">
                  Risk {Math.round(row.avg_risk_score)} · {riskLabelFromScore(row.avg_risk_score)}
                </div>
                <div className="text-xs text-muted-foreground">Complaints {row.open_complaints}</div>
                <div className={cn(
                  "text-xs font-medium capitalize",
                  row.effectiveness_label === "strong" ? "text-emerald" : row.effectiveness_label === "needs_support" ? "text-danger" : "text-warning",
                )}>
                  {Math.round(row.effectiveness_score)} · {row.effectiveness_label.replaceAll("_", " ")}
                </div>
              </li>
            ))}
            {managerEffectiveness.length === 0 && (
              <li className="px-5 py-6 text-sm text-muted-foreground">No manager effectiveness data yet.</li>
            )}
          </ul>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Automation rules</div>
              <div className="text-sm mt-1">Admin-configurable workflow automation</div>
            </div>
            <div className="flex flex-wrap gap-2 justify-end">
              <button
                type="button"
                onClick={() => void createDefaultEscalationRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-ink text-primary-foreground text-xs"
              >
                <Plus className="size-3.5" />
                Add complaint escalation
              </button>
              <button
                type="button"
                onClick={() => void createStatusRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add ticket status rule
              </button>
              <button
                type="button"
                onClick={() => void createLeaveReviewRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add leave review rule
              </button>
              <button
                type="button"
                onClick={() => void createWellbeingAlertRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add wellbeing alert rule
              </button>
              <button
                type="button"
                onClick={() => void createTicketCloseFollowupRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add ticket close workflow
              </button>
              <button
                type="button"
                onClick={() => void createInternalNoteEscalationRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add internal note workflow
              </button>
              <button
                type="button"
                onClick={() => void createLeaveRequestedRule()}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              >
                <Plus className="size-3.5" />
                Add leave requested workflow
              </button>
            </div>
          </div>
          <ul className="divide-y divide-border">
            {automationRules.map((rule) => (
              <li key={rule.id} className="px-5 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{rule.name}</div>
                  <div className="text-xs text-muted-foreground">Event: {rule.event_type} · Actions: {Object.keys(rule.actions || {}).join(", ") || "none"}</div>
                </div>
                <button
                  type="button"
                  onClick={() => void toggleRule(rule)}
                  className={cn(
                    "text-xs px-2.5 py-1 rounded-md border",
                    rule.enabled ? "bg-emerald-soft text-emerald border-emerald/40" : "bg-secondary text-muted-foreground border-border",
                  )}
                >
                  {rule.enabled ? "Enabled" : "Disabled"}
                </button>
              </li>
            ))}
            {automationRules.length === 0 && (
              <li className="px-5 py-6 text-sm text-muted-foreground">No automation rules yet.</li>
            )}
          </ul>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Proactive suppression policy</div>
              <div className="text-sm mt-1">Nudge/reminder anti-spam controls</div>
            </div>
            <button
              type="button"
              onClick={() => void saveProactivePolicy()}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-ink text-primary-foreground text-xs"
              disabled={!proactivePolicy}
            >
              Save policy
            </button>
          </div>
          {!proactivePolicy ? (
            <div className="px-5 py-6 text-sm text-muted-foreground">Policy data unavailable.</div>
          ) : (
            <div className="px-5 py-4 grid md:grid-cols-2 gap-4">
              <label className="text-xs text-muted-foreground flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={proactivePolicy.enabled}
                  onChange={(e) => setProactivePolicy((prev) => (prev ? { ...prev, enabled: e.target.checked } : prev))}
                />
                Enable suppression
              </label>
              <FieldNumber
                label="Global daily max"
                value={proactivePolicy.global_daily_max}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, global_daily_max: value } : prev))}
              />
              <FieldNumber
                label="Break nudge cooldown (min)"
                value={proactivePolicy.break_nudge_cooldown_minutes}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, break_nudge_cooldown_minutes: value } : prev))}
              />
              <FieldNumber
                label="Break nudge daily max"
                value={proactivePolicy.break_nudge_daily_max}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, break_nudge_daily_max: value } : prev))}
              />
              <FieldNumber
                label="Reminder cooldown (min)"
                value={proactivePolicy.scheduled_reminder_cooldown_minutes}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, scheduled_reminder_cooldown_minutes: value } : prev))}
              />
              <FieldNumber
                label="Reminder daily max"
                value={proactivePolicy.scheduled_reminder_daily_max}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, scheduled_reminder_daily_max: value } : prev))}
              />
              <FieldNumber
                label="Follow-up cooldown (min)"
                value={proactivePolicy.daily_checkin_followup_cooldown_minutes}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, daily_checkin_followup_cooldown_minutes: value } : prev))}
              />
              <FieldNumber
                label="Follow-up daily max"
                value={proactivePolicy.daily_checkin_followup_daily_max}
                onChange={(value) => setProactivePolicy((prev) => (prev ? { ...prev, daily_checkin_followup_daily_max: value } : prev))}
              />
            </div>
          )}
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Integrations</div>
            <div className="text-sm mt-1">Calendar + HRMS + payroll connectors</div>
          </div>
          <ul className="divide-y divide-border">
            {integrations.map((provider) => (
              <li key={provider.key} className="px-5 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{provider.key.replaceAll("_", " ")}</div>
                  <div className="text-xs text-muted-foreground">
                    {provider.category.toUpperCase()} · {provider.configured ? "Configured" : "Not configured"} · {provider.status}
                  </div>
                  {provider.notes && <div className="text-xs text-muted-foreground mt-1">{provider.notes}</div>}
                </div>
                {(provider.category === "hrms" || provider.category === "payroll") && (
                  <button
                    type="button"
                    onClick={() => void runIntegrationSync(provider)}
                    disabled={syncBusyKey === provider.key}
                    className="text-xs px-2.5 py-1 rounded-md border border-border bg-secondary hover:bg-secondary/70 disabled:opacity-50"
                  >
                    {syncBusyKey === provider.key ? "Running..." : "Run dry sync"}
                  </button>
                )}
              </li>
            ))}
            {integrations.length === 0 && (
              <li className="px-5 py-6 text-sm text-muted-foreground">Integration providers unavailable.</li>
            )}
          </ul>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Proactive risk watch</div>
              <div className="text-sm mt-1">Live wellbeing risk + weekly rollup</div>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs"
              onClick={() => {
                void getWellbeingHighRisk(8).then(setHighRiskRows);
                void getWeeklyWellbeingSummary().then(setWeeklySummary);
              }}
            >
              Refresh
            </button>
          </div>
          <div className="px-5 py-4 border-b border-border grid md:grid-cols-4 gap-3 text-xs text-muted-foreground">
            <div>High risk: <span className="text-foreground font-medium">{weeklySummary?.high_risk_employees ?? 0}</span></div>
            <div>Follow-up signals: <span className="text-foreground font-medium">{weeklySummary?.followup_signals ?? 0}</span></div>
            <div>Open tickets: <span className="text-foreground font-medium">{weeklySummary?.open_tickets ?? 0}</span></div>
            <div>Avg engagement: <span className="text-foreground font-medium">{weeklySummary?.avg_engagement_score ?? 0}</span></div>
          </div>
          <ul className="divide-y divide-border">
            {highRiskRows.map((row) => (
              <li key={row.user_id} className="px-5 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{row.name}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    Risk {Math.round(row.risk_score)} · {riskLabelFromScore(row.risk_score)} · Mood {Math.round(row.mood_score)} · {row.last_active}
                  </div>
                  {row.reasons[0] && <div className="text-xs text-muted-foreground mt-1 truncate">{row.reasons[0]}</div>}
                </div>
                <span className={cn(
                  "text-[11px] px-2 py-1 rounded-md border capitalize",
                  row.risk_level === "high"
                    ? "bg-danger-soft text-danger border-danger/40"
                    : row.risk_level === "medium"
                      ? "bg-warning-soft text-warning border-warning/40"
                      : "bg-emerald-soft text-emerald border-emerald/40",
                )}>
                  {row.risk_level}
                </span>
              </li>
            ))}
            {highRiskRows.length === 0 && (
              <li className="px-5 py-6 text-sm text-muted-foreground">No high-risk rows returned yet.</li>
            )}
          </ul>
        </div>
      </div>
      {inviteOpen && (
        <InviteUserDialog
          onClose={() => setInviteOpen(false)}
          onInvited={() => {
            setInviteOpen(false);
            void refreshUsers();
          }}
        />
      )}
    </AppLayout>
  );
}

function InviteUserDialog({ onClose, onInvited }: { onClose: () => void; onInvited: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("employee");
  const [designation, setDesignation] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim() || !email.trim()) {
      toast.error("Name and email are required.");
      return;
    }
    setBusy(true);
    const result = await inviteUser({
      name: name.trim(),
      email: email.trim(),
      role,
      designation: designation.trim() || undefined,
    });
    setBusy(false);
    if (!result) {
      toast.error("Could not invite user — they may already exist.");
      return;
    }
    if (result.invite_email_sent) {
      toast.success(`Invite emailed to ${result.email}.`);
    } else {
      toast.success(`User created. Temporary password: ${result.temp_password}`, { duration: 12000 });
    }
    onInvited();
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6" onClick={(e) => e.stopPropagation()}>
        <div className="text-sm font-medium mb-1">Invite a user</div>
        <div className="text-xs text-muted-foreground mb-4">
          A temporary password is generated. We email the invite when SMTP is configured, otherwise the password is shown once here.
        </div>
        <div className="space-y-3">
          <label className="block text-xs text-muted-foreground">
            <div className="mb-1">Full name</div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
              placeholder="Jane Doe"
            />
          </label>
          <label className="block text-xs text-muted-foreground">
            <div className="mb-1">Work email</div>
            <input
              value={email}
              type="email"
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
              placeholder="jane@company.com"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs text-muted-foreground">
              <div className="mb-1">Role</div>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground capitalize"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-muted-foreground">
              <div className="mb-1">Designation</div>
              <input
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                className="w-full h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                placeholder="Optional"
              />
            </label>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-2 rounded-lg border border-border text-sm">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={busy}
            className="px-3 py-2 rounded-lg bg-ink text-primary-foreground text-sm disabled:opacity-50"
          >
            {busy ? "Inviting…" : "Send invite"}
          </button>
        </div>
      </div>
    </div>
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

function FieldNumber({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="text-xs text-muted-foreground">
      <div className="mb-1">{label}</div>
      <input
        type="number"
        value={value}
        min={0}
        onChange={(e) => onChange(Number(e.target.value || 0))}
        className="w-full h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
      />
    </label>
  );
}

function riskLabelFromScore(score: number): "Low" | "Medium" | "High" {
  if (score >= 70) return "High";
  if (score >= 40) return "Medium";
  return "Low";
}

function sentimentTrendLabel(score: number): string {
  if (score < 45) return "↓ declining";
  if (score > 65) return "↑ improving";
  return "→ stable";
}
