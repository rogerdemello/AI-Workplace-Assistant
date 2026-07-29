import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { getAdminUsers, getEmployees, getTickets } from "@/lib/services";
import type { Ticket } from "@/lib/domain-types";
import { PriorityPill, StatusPill, Avatar } from "@/components/ui-bits";
import { Search, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { TicketDecisionPanel } from "@/components/tickets/TicketDecisionPanel";
import { buildTicketDetailView, type TicketDetailView } from "@/components/tickets/ticket-insights";
import { subscribeToSse } from "@/lib/api/client";

export default function Tickets() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { session } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [nameByUserId, setNameByUserId] = useState<Record<string, string>>({});
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [status, setStatus] = useState<string>(searchParams.get("status") || "all");
  const [priority, setPriority] = useState<string>(searchParams.get("priority") || "all");
  const [selected, setSelected] = useState<TicketDetailView | null>(null);

  const refreshTickets = () => {
    void getTickets().then((rows) => {
      setTickets(rows);
      if (!selected) return;
      const next = buildTicketDetailView(rows).find((t) => t.id === selected.id) || null;
      setSelected(next);
    });
  };

  useEffect(() => {
    refreshTickets();
    if (session?.role === "hr") {
      Promise.all([getEmployees(), getAdminUsers()]).then(([employeeList, adminList]) => {
        const next: Record<string, string> = {};
        employeeList.forEach((e) => {
          next[e.id] = e.name;
        });
        adminList.forEach((u) => {
          next[u.id] = u.name;
        });
        setNameByUserId(next);
      });
    }

    const unsubscribe = subscribeToSse("/api/v1/realtime/hr/stream", {
      onEvent: (eventType) => {
        if (eventType === "hr_snapshot") refreshTickets();
      },
    });
    const refreshTimer = window.setInterval(() => {
      refreshTickets();
    }, 45000);

    return () => {
      unsubscribe();
      window.clearInterval(refreshTimer);
    };
  }, [session?.role]);

  const raisedByLabel = (userId: string) => {
    if (session?.userId && userId === session.userId) return "You";
    return nameByUserId[userId] || "Employee";
  };

  const initialsFor = (label: string) =>
    label
      .split(/\s+/)
      .map((p) => p[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "EM";

  const viewModel = useMemo(() => buildTicketDetailView(tickets), [tickets]);

  const filtered = useMemo(() => viewModel.filter((t) => {
    if (status !== "all" && t.status !== status) return false;
    if (priority !== "all" && t.priority !== priority) return false;
    if (q && !(t.title + t.summary + t.id).toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [viewModel, q, status, priority]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    if (status !== "all") next.set("status", status);
    if (priority !== "all") next.set("priority", priority);
    setSearchParams(next, { replace: true });
  }, [q, status, priority, setSearchParams]);

  const exportCsv = () => {
    const header = ["ID", "Title", "Summary", "Status", "Priority", "RaisedBy", "SlaRemainingHours"];
    const rows = filtered.map((ticket) => [
      ticket.id,
      ticket.title,
      ticket.summary,
      ticket.status,
      ticket.priority,
      raisedByLabel(ticket.raisedBy || ""),
      String(ticket.slaRemainingHours),
    ]);
    const csv = [header, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "tickets-filtered.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppLayout
      title="Tickets"
      subtitle={session?.role === "hr" ? "Everything employees have raised — surfaced from chat" : "Your requests to HR"}
    >
      <div className="px-6 lg:px-10 py-8 max-w-7xl">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex items-center gap-2 px-3 h-10 rounded-lg bg-card border border-border w-72">
            <Search className="size-4 text-muted-foreground" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tickets…" className="flex-1 bg-transparent text-sm outline-none" />
          </div>
          <Pills label="Status" value={status} onChange={setStatus} options={[["all","All"],["open","Open"],["in_progress","In progress"],["escalated","Escalated"],["resolved","Resolved"]]} />
          <Pills label="Priority" value={priority} onChange={setPriority} options={[["all","All"],["critical","Critical"],["high","High"],["medium","Medium"],["low","Low"]]} />
          <button
            onClick={exportCsv}
            className="ml-auto text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary transition-colors"
          >
            Export CSV
          </button>
          <div className="text-xs text-muted-foreground">{filtered.length} of {tickets.length}</div>
        </div>

        {/* List */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="hidden md:grid grid-cols-[100px_1fr_120px_100px_140px_80px] px-5 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground border-b border-border">
            <div>ID</div><div>Subject</div><div>Status</div><div>Priority</div><div>Raised by</div><div>SLA</div>
          </div>
          <ul className="divide-y divide-border">
            {filtered.map((t) => {
              const uid = t.raisedBy || "";
              const raisedByName = raisedByLabel(uid);
              const slaPct = (t.slaRemainingHours / t.slaHours) * 100;
              const slaCls = slaPct < 25 ? "text-danger" : slaPct < 50 ? "text-warning" : "text-muted-foreground";
              return (
                <li key={t.id} onClick={() => setSelected(t)} className="grid md:grid-cols-[100px_1fr_120px_100px_140px_80px] gap-3 items-center px-5 py-4 hover:bg-secondary/40 cursor-pointer transition-colors">
                  <div className="text-xs font-mono text-muted-foreground">{t.id}</div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{t.title}</div>
                    <div className="text-xs text-muted-foreground truncate">{t.summary}</div>
                  </div>
                  <div><StatusPill status={t.status} /></div>
                  <div><PriorityPill priority={t.priority} /></div>
                  <div className="flex items-center gap-2 min-w-0">
                    <Avatar initials={initialsFor(raisedByName)} size="sm" />
                    <div className="text-xs truncate">{raisedByName}</div>
                  </div>
                  <div className={cn("text-xs flex items-center gap-1", slaCls)}>
                    <Clock className="size-3" />{t.slaRemainingHours}h
                  </div>
                </li>
              );
            })}
          </ul>
          {filtered.length === 0 && (
            <div className="px-5 py-8 text-sm text-muted-foreground">Ticket data unavailable until endpoint exists.</div>
          )}
        </div>
      </div>

      <TicketDecisionPanel selected={selected} setSelected={setSelected} nameByUserId={nameByUserId} raisedByLabel={raisedByLabel} onTicketUpdated={refreshTickets} />
    </AppLayout>
  );
}

function Pills({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground hidden lg:inline">{label}:</span>
      <div className="flex gap-1 p-1 rounded-lg bg-secondary">
        {options.map(([v, l]) => (
          <button key={v} onClick={() => onChange(v)} className={cn(
            "text-xs px-2.5 py-1 rounded-md transition-colors",
            value === v ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
          )}>{l}</button>
        ))}
      </div>
    </div>
  );
}
