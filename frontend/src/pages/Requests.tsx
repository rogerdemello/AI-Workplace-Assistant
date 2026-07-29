import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Avatar } from "@/components/ui-bits";
import { CalendarClock, FileText, Receipt, RefreshCw, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { subscribeToSse } from "@/lib/api/client";
import {
  approveRequest,
  cancelRequest,
  completeRequest,
  getRequestSummary,
  listRequests,
  rejectRequest,
  scheduleRequest,
  type EmployeeRequestRow,
  type RequestStatus,
  type RequestSummary,
  type RequestType,
} from "@/lib/api/requests";

const TYPE_META: Record<RequestType, { label: string; icon: typeof FileText }> = {
  appointment: { label: "Appointment", icon: CalendarClock },
  expense: { label: "Expense", icon: Receipt },
  shift_change: { label: "Shift change", icon: RefreshCw },
  document: { label: "Document", icon: FileText },
};

const STATUS_TONE: Record<RequestStatus, string> = {
  pending: "bg-warning/10 text-warning border-warning/20",
  scheduled: "bg-primary/10 text-primary border-primary/20",
  approved: "bg-success/10 text-success border-success/20",
  completed: "bg-success/10 text-success border-success/20",
  rejected: "bg-danger/10 text-danger border-danger/20",
  cancelled: "bg-muted text-muted-foreground border-border",
};

const TERMINAL: RequestStatus[] = ["rejected", "cancelled", "completed"];

export default function Requests() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { session } = useAuth();
  const isReviewer = session?.role === "hr" || session?.role === "admin";

  const [rows, setRows] = useState<EmployeeRequestRow[]>([]);
  const [summary, setSummary] = useState<RequestSummary | null>(null);
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [typeFilter, setTypeFilter] = useState(searchParams.get("type") || "all");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "all");
  const [selected, setSelected] = useState<EmployeeRequestRow | null>(null);
  const [note, setNote] = useState("");
  const [slot, setSlot] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextRows, nextSummary] = await Promise.all([listRequests(), getRequestSummary()]);
    setRows(nextRows);
    setSummary(nextSummary);
    setSelected((current) => (current ? nextRows.find((r) => r.id === current.id) ?? null : null));
  }, []);

  useEffect(() => {
    void refresh();

    // The HR stream is role-gated (403 for employees), so employees follow their
    // own per-user stream instead.
    const stream = isReviewer ? "/api/v1/realtime/hr/stream" : "/api/v1/realtime/me/stream";
    const unsubscribe = subscribeToSse(stream, {
      onEvent: (eventType) => {
        if (eventType.startsWith("hr_request_") || eventType === "hr_snapshot") void refresh();
      },
    });
    const timer = window.setInterval(() => void refresh(), 45000);

    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, [refresh, isReviewer]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    if (typeFilter !== "all") next.set("type", typeFilter);
    if (statusFilter !== "all") next.set("status", statusFilter);
    setSearchParams(next, { replace: true });
  }, [q, typeFilter, statusFilter, setSearchParams]);

  useEffect(() => {
    setNote(selected?.hrNote ?? "");
    setSlot(selected?.scheduledAt ? selected.scheduledAt.slice(0, 16) : "");
    setError(null);
  }, [selected?.id]);

  const filtered = useMemo(
    () =>
      rows.filter((row) => {
        if (typeFilter !== "all" && row.requestType !== typeFilter) return false;
        if (statusFilter !== "all" && row.status !== statusFilter) return false;
        if (q) {
          const haystack = `${row.title} ${row.employeeName ?? ""} ${JSON.stringify(row.details)}`;
          if (!haystack.toLowerCase().includes(q.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, q, typeFilter, statusFilter],
  );

  const act = async (action: () => Promise<EmployeeRequestRow | null>) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await action();
      if (!updated) {
        setError("That didn't go through. Please try again.");
        return;
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const initialsFor = (label: string) =>
    label
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "EM";

  return (
    <AppLayout
      title="Requests"
      subtitle={
        isReviewer
          ? "Appointments, expenses, shift changes and documents raised through chat"
          : "What you've asked Mark to sort out for you"
      }
    >
      <div className="px-6 lg:px-10 py-8 max-w-7xl">
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <SummaryTile label="Pending" value={summary.pending} tone="warning" />
            <SummaryTile label="Scheduled" value={summary.scheduled} tone="primary" />
            <SummaryTile label="Approved" value={summary.approved} tone="success" />
            <SummaryTile label="Completed" value={summary.completed} tone="muted" />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex items-center gap-2 px-3 h-10 rounded-lg bg-card border border-border w-72">
            <Search className="size-4 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search requests…"
              className="flex-1 bg-transparent text-sm outline-none"
            />
          </div>
          <Pills
            label="Type"
            value={typeFilter}
            onChange={setTypeFilter}
            options={[
              ["all", "All"],
              ["appointment", "Appointments"],
              ["expense", "Expenses"],
              ["shift_change", "Shift"],
              ["document", "Documents"],
            ]}
          />
          <Pills
            label="Status"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              ["all", "All"],
              ["pending", "Pending"],
              ["scheduled", "Scheduled"],
              ["approved", "Approved"],
              ["rejected", "Rejected"],
            ]}
          />
          <div className="ml-auto text-xs text-muted-foreground">
            {filtered.length} of {rows.length}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="hidden md:grid grid-cols-[140px_1fr_150px_120px_130px] px-5 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground border-b border-border">
            <div>Type</div>
            <div>Request</div>
            <div>Raised by</div>
            <div>Status</div>
            <div>When</div>
          </div>
          <ul className="divide-y divide-border">
            {filtered.map((row) => {
              const meta = TYPE_META[row.requestType];
              const Icon = meta.icon;
              const who =
                session?.userId && row.userId === session.userId
                  ? "You"
                  : row.employeeName || "Employee";
              return (
                <li
                  key={row.id}
                  onClick={() => setSelected(row)}
                  className="grid md:grid-cols-[140px_1fr_150px_120px_130px] gap-3 items-center px-5 py-4 hover:bg-secondary/40 cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Icon className="size-3.5" />
                    {meta.label}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{row.title}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {describeDetails(row)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 min-w-0">
                    <Avatar initials={initialsFor(who)} size="sm" />
                    <div className="text-xs truncate">{who}</div>
                  </div>
                  <div>
                    <span
                      className={cn(
                        "text-[11px] px-2 py-0.5 rounded-full border capitalize",
                        STATUS_TONE[row.status],
                      )}
                    >
                      {row.status}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatDate(row.scheduledAt ?? row.startDate ?? row.createdAt)}
                  </div>
                </li>
              );
            })}
          </ul>
          {filtered.length === 0 && (
            <div className="px-5 py-8 text-sm text-muted-foreground">
              Nothing here yet. Requests appear as soon as employees raise them with Mark.
            </div>
          )}
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setSelected(null)}>
          <aside
            className="w-full max-w-md h-full bg-card border-l border-border overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-border">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-1">
                {TYPE_META[selected.requestType].label}
              </div>
              <h2 className="text-lg font-semibold">{selected.title}</h2>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={cn(
                    "text-[11px] px-2 py-0.5 rounded-full border capitalize",
                    STATUS_TONE[selected.status],
                  )}
                >
                  {selected.status}
                </span>
                <span className="text-xs text-muted-foreground">
                  {selected.employeeName || "Employee"} · {formatDate(selected.createdAt)}
                </span>
              </div>
            </div>

            <div className="px-6 py-5 space-y-4">
              <dl className="space-y-2">
                {Object.entries(selected.details).map(([key, value]) => (
                  <div key={key} className="flex gap-3 text-sm">
                    <dt className="w-32 shrink-0 text-muted-foreground capitalize">
                      {key.replaceAll("_", " ")}
                    </dt>
                    <dd className="min-w-0 break-words">{String(value)}</dd>
                  </div>
                ))}
              </dl>

              {isReviewer && !TERMINAL.includes(selected.status) && (
                <div className="space-y-3 pt-2 border-t border-border">
                  <label className="block text-xs text-muted-foreground">
                    Note to the employee (optional)
                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      rows={3}
                      className="mt-1 w-full rounded-lg border border-border bg-background p-2 text-sm text-foreground outline-none"
                    />
                  </label>

                  {selected.requestType === "appointment" && (
                    <label className="block text-xs text-muted-foreground">
                      Confirmed slot
                      <input
                        type="datetime-local"
                        value={slot}
                        onChange={(e) => setSlot(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-border bg-background p-2 text-sm text-foreground outline-none"
                      />
                    </label>
                  )}

                  {error && <p className="text-xs text-danger">{error}</p>}

                  <div className="flex flex-wrap gap-2">
                    {selected.requestType === "appointment" && (
                      <button
                        disabled={busy || !slot}
                        onClick={() => void act(() => scheduleRequest(selected.id, slot, note))}
                        className="text-xs px-3 h-8 rounded-md bg-primary text-primary-foreground disabled:opacity-50"
                      >
                        Confirm slot
                      </button>
                    )}
                    <button
                      disabled={busy}
                      onClick={() => void act(() => approveRequest(selected.id, note))}
                      className="text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void act(() => completeRequest(selected.id, note))}
                      className="text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary disabled:opacity-50"
                    >
                      Mark done
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void act(() => rejectRequest(selected.id, note))}
                      className="text-xs px-3 h-8 rounded-md border border-danger/30 text-danger hover:bg-danger/5 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )}

              {!isReviewer &&
                selected.userId === session?.userId &&
                !TERMINAL.includes(selected.status) && (
                  <button
                    disabled={busy}
                    onClick={() => void act(() => cancelRequest(selected.id))}
                    className="text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary disabled:opacity-50"
                  >
                    Withdraw request
                  </button>
                )}

              {selected.hrNote && (
                <div className="pt-2 border-t border-border">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-1">
                    HR note
                  </div>
                  <p className="text-sm">{selected.hrNote}</p>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </AppLayout>
  );
}

function describeDetails(row: EmployeeRequestRow): string {
  switch (row.requestType) {
    case "appointment":
      return [row.details.topic, row.details.mode].filter(Boolean).join(" · ") || "1:1 with HR";
    case "expense":
      return [row.amount != null ? row.amount.toLocaleString() : null, row.details.description]
        .filter(Boolean)
        .join(" · ");
    case "shift_change":
      return [row.details.change_type, row.details.reason].filter(Boolean).join(" · ");
    case "document":
      return String(row.details.purpose ?? "");
    default:
      return "";
  }
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "warning" | "primary" | "success" | "muted";
}) {
  const toneCls = {
    warning: "text-warning",
    primary: "text-primary",
    success: "text-success",
    muted: "text-muted-foreground",
  }[tone];
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className={cn("text-2xl font-semibold mt-1", toneCls)}>{value}</div>
    </div>
  );
}

function Pills({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground hidden lg:inline">{label}:</span>
      <div className="flex gap-1 p-1 rounded-lg bg-secondary">
        {options.map(([v, l]) => (
          <button
            key={v}
            onClick={() => onChange(v)}
            className={cn(
              "text-xs px-2.5 py-1 rounded-md transition-colors",
              value === v
                ? "bg-card text-foreground shadow-soft"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}
