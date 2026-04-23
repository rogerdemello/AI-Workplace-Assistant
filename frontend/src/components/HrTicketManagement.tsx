"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  addTicketMessage,
  getTicketAssignees,
  getTickets,
  listTicketMessages,
  updateTicket,
  type TicketAssigneeResponse,
  type TicketMessageResponse,
  type TicketPriority,
  type TicketResponse,
  type TicketStatus as ApiTicketStatus,
} from '@/lib/api';
import type { TicketRow, TicketStatus as UiTicketStatus } from '@/lib/hr-data';
import { mapFastApiTicketToRow } from '@/lib/hr-data';

const FILTER_ALL = "all";
const UNASSIGNED = "unassigned";

const UI_TO_API: Record<UiTicketStatus, ApiTicketStatus> = {
  Open: "open",
  "In Review": "in_progress",
  Escalated: "escalated",
  Resolved: "resolved",
  Closed: "closed",
};

const STATUS_OPTIONS: UiTicketStatus[] = ["Open", "In Review", "Escalated", "Resolved", "Closed"];
const PRIORITY_OPTIONS: TicketPriority[] = ['low', 'medium', 'high', 'critical'];

interface TicketDraft {
  status: UiTicketStatus;
  priority: TicketPriority;
  assignedTo: string;
}

interface HrTicketManagementProps {
  initialRows: TicketRow[];
  onTicketsChanged?: () => void;
}

export function HrTicketManagement({ initialRows, onTicketsChanged }: HrTicketManagementProps) {
  const [rows, setRows] = useState<TicketRow[]>(initialRows);
  const [assignees, setAssignees] = useState<TicketAssigneeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>(FILTER_ALL);

  // ── Unified modal state: set atomically so Select values never render blank ──
  const [openedModal, setOpenedModal] = useState<{
    id: string;
    draft: TicketDraft;
  } | null>(null);

  // Convenience aliases kept so the rest of the component doesn't need to change
  const detailId = openedModal?.id ?? null;
  const ticketDraft = openedModal?.draft ?? null;
  const setDetailId = (id: string | null) => {
    if (id === null) setOpenedModal(null);
  };
  const setTicketDraft = (updater: ((prev: TicketDraft | null) => TicketDraft | null) | TicketDraft | null) => {
    setOpenedModal((prev) => {
      if (!prev) return null;
      const next = typeof updater === 'function' ? updater(prev.draft) : updater;
      return next ? { ...prev, draft: next } : null;
    });
  };

  const [messages, setMessages] = useState<TicketMessageResponse[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async (): Promise<TicketRow[] | null> => {
    setLoading(true);
    setError(null);
    try {
      const list = await getTickets();
      const mapped = (list as TicketResponse[]).map(mapFastApiTicketToRow);
      setRows(mapped);
      onTicketsChanged?.();
      return mapped;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
      return null;
    } finally {
      setLoading(false);
    }
  }, [onTicketsChanged]);

  useEffect(() => {
    setRows(initialRows);
  }, [initialRows]);

  useEffect(() => {
    const loadAssignees = async () => {
      try {
        const data = await getTicketAssignees();
        setAssignees(data);
      } catch {
        setAssignees([]);
      }
    };
    void loadAssignees();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      const statusOk = filterStatus === FILTER_ALL || r.status === filterStatus;
      const textOk =
        !q ||
        r.issue.toLowerCase().includes(q) ||
        r.employeeId.toLowerCase().includes(q) ||
        r.against.toLowerCase().includes(q);
      return statusOk && textOk;
    });
  }, [rows, search, filterStatus]);

  const detailTicket = useMemo(() => {
    if (!detailId) return null;
    return rows.find((row) => row.id === detailId) ?? null;
  }, [rows, detailId]);

  const openDetail = async (id: string) => {
    const row = rows.find((ticket) => ticket.id === id);
    // Set the modal state atomically — draft is never null when modal opens
    setOpenedModal({
      id,
      draft: {
        status: row?.status ?? 'Open',
        priority: row?.priority ?? 'medium',
        assignedTo: row?.assignedTo ?? UNASSIGNED,
      },
    });
    setComment("");
    setMsgLoading(true);
    try {
      const m = await listTicketMessages(id);
      setMessages(m);
    } catch {
      setMessages([]);
    } finally {
      setMsgLoading(false);
    }
  };

  const applyTicketUpdate = async () => {
    if (!detailId || !ticketDraft) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await updateTicket(detailId, {
        status: UI_TO_API[ticketDraft.status],
        priority: ticketDraft.priority,
        assigned_to: ticketDraft.assignedTo === UNASSIGNED ? null : ticketDraft.assignedTo,
      });

      const latestRows = await refresh();
      if (latestRows) {
        const updated = latestRows.find((row) => row.id === detailId);
        if (updated) {
          setTicketDraft({
            status: updated.status,
            priority: updated.priority ?? 'medium',
            assignedTo: updated.assignedTo ?? UNASSIGNED,
          });
        }
      }

      const m = await listTicketMessages(detailId);
      setMessages(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  const sendComment = async () => {
    if (!detailId || !comment.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await addTicketMessage(detailId, comment.trim());
      setComment("");
      const m = await listTicketMessages(detailId);
      setMessages(m);
      onTicketsChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add comment");
    } finally {
      setSaving(false);
    }
  };

  const priorityBadge = (priority: TicketPriority | undefined) => {
    const value = priority ?? 'medium';
    const map: Record<TicketPriority, string> = {
      low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      medium: 'bg-blue-50 text-blue-700 border-blue-200',
      high: 'bg-amber-50 text-amber-700 border-amber-200',
      critical: 'bg-rose-50 text-rose-700 border-rose-200',
    };
    return map[value];
  };

  const slaMeta = (ticket: TicketRow): { text: string; className: string } => {
    if (!ticket.slaDueAt) {
      return { text: '-', className: 'text-slate-400' };
    }

    if (ticket.status === 'Resolved' || ticket.status === 'Closed') {
      return { text: 'Met/Closed', className: 'text-slate-400' };
    }

    const dueMs = new Date(ticket.slaDueAt).getTime();
    if (Number.isNaN(dueMs)) {
      return { text: '-', className: 'text-slate-400' };
    }

    if (dueMs < Date.now()) {
      return { text: 'Overdue', className: 'text-rose-600 font-semibold' };
    }

    if (ticket.slaWarning) {
      return {
        text: new Date(ticket.slaDueAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        className: 'text-amber-600 font-medium',
      };
    }

    return {
      text: new Date(ticket.slaDueAt).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
      className: 'text-slate-600',
    };
  };

  const isTicketOverdue = (ticket: TicketRow): boolean => {
    if (!ticket.slaDueAt) return false;
    if (ticket.status === 'Resolved' || ticket.status === 'Closed') return false;
    const dueMs = new Date(ticket.slaDueAt).getTime();
    if (Number.isNaN(dueMs)) return false;
    return dueMs < Date.now();
  };

  const assigneeName = (id: string | null | undefined): string => {
    if (!id) return 'Unassigned';
    const user = assignees.find((row) => row.id === id);
    return user?.name ?? 'Assigned';
  };

  const statusBadge = (s: UiTicketStatus) => {
    const map: Record<UiTicketStatus, string> = {
      Open: "bg-slate-100 text-slate-700 border-slate-200",
      "In Review": "bg-blue-50 text-blue-700 border-blue-200",
      Resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
      Escalated: "bg-rose-50 text-rose-700 border-rose-200",
      Closed: "bg-slate-100 text-slate-700 border-slate-200",
    };
    return map[s] ?? map.Open;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-end">
          <div className="max-w-md flex-1">
            <Label className="text-xs text-slate-500">Search</Label>
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Issue, employee id, category…"
              className="mt-1 h-10 rounded-xl bg-slate-50"
            />
          </div>
          <div className="w-full sm:w-48">
            <Label className="text-xs text-slate-500">Status</Label>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="mt-1 rounded-xl">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FILTER_ALL}>All statuses</SelectItem>
                {STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button type="button" variant="outline" className="rounded-full" onClick={() => void refresh()} disabled={loading}>
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>
      ) : null}

      <div className="overflow-x-auto rounded-2xl border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-3 pl-4 pr-4 font-semibold">Employee ID</th>
              <th className="py-3 pr-4 font-semibold">Issue</th>
              <th className="py-3 pr-4 font-semibold">Category</th>
              <th className="py-3 pr-4 font-semibold">Priority</th>
              <th className="py-3 pr-4 font-semibold">Status</th>
              <th className="py-3 pr-4 font-semibold">SLA</th>
              <th className="py-3 pr-4 font-semibold">Assignee</th>
              <th className="py-3 pr-4 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((ticket) => {
              const canResolve = !['Resolved', 'Closed'].includes(ticket.status);
              const canEscalate = !['Escalated', 'Resolved', 'Closed'].includes(ticket.status);

              const quickAction = async (action: 'resolve' | 'escalate') => {
                const newStatus = action === 'resolve' ? 'resolved' : 'escalated';
                try {
                  await updateTicket(ticket.id, { status: newStatus as ApiTicketStatus });
                  await refresh();
                } catch {
                  // ignore — refresh will show current state
                }
              };

              return (
                <tr key={ticket.id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-3 pl-4 pr-4 font-medium text-slate-900">{ticket.employeeId}</td>
                  <td className="max-w-xs py-3 pr-4 text-slate-600 truncate" title={ticket.issue}>{ticket.issue}</td>
                  <td className="py-3 pr-4 text-slate-600">{ticket.against}</td>
                  <td className="py-3 pr-4">
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${priorityBadge(ticket.priority)}`} data-testid="ticket-priority">
                      {(ticket.priority ?? 'medium').toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold ${statusBadge(ticket.status)}`} data-testid="ticket-status">
                      {ticket.status === 'Escalated' && <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse inline-block" />}
                      {ticket.status || 'Open'}
                    </span>
                  </td>
                  <td className={`py-3 pr-4 text-sm ${slaMeta(ticket).className}`}>
                    {isTicketOverdue(ticket) && <span className="mr-1 h-2 w-2 rounded-full bg-red-500 animate-pulse inline-block" />}
                    {slaMeta(ticket).text}
                  </td>
                  <td className="py-3 pr-4 text-slate-600" data-testid="ticket-assignee">{assigneeName(ticket.assignedTo)}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-1">
                      {canResolve && (
                        <Button
                          type="button" size="sm" variant="ghost"
                          className="h-7 w-7 rounded-full p-0 text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700"
                          title="Resolve"
                          onClick={() => void quickAction('resolve')}
                        >✓</Button>
                      )}
                      {canEscalate && (
                        <Button
                          type="button" size="sm" variant="ghost"
                          className="h-7 w-7 rounded-full p-0 text-amber-600 hover:bg-amber-50 hover:text-amber-700"
                          title="Escalate"
                          onClick={() => void quickAction('escalate')}
                        >↑</Button>
                      )}
                      <Button
                        type="button" size="sm" variant="outline"
                        className="rounded-full text-xs px-3" onClick={() => void openDetail(ticket.id)}
                      >
                        Manage
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-slate-500">No tickets match the current filters.</p>
        ) : null}
      </div>

      {detailId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-start justify-between gap-4">
              <h3 className="text-lg font-semibold text-slate-900">Ticket</h3>
              <Button type="button" variant="ghost" size="sm" className="rounded-full" onClick={() => setDetailId(null)}>
                Close
              </Button>
            </div>
            {!detailTicket ? (
              <p className="text-sm text-slate-500">Ticket not found.</p>
            ) : (
              <>
                <p className="text-sm text-slate-600">{detailTicket.issue}</p>
                <p className="mt-2 text-xs text-slate-400">Employee: {detailTicket.employeeId}</p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="text-xs text-slate-500">Status</Label>
                    <Select
                      value={ticketDraft?.status ?? 'Open'}
                      defaultValue={ticketDraft?.status ?? 'Open'}
                      onValueChange={(v) =>
                        setTicketDraft((prev) => (prev ? { ...prev, status: v as UiTicketStatus } : prev))
                      }
                      disabled={saving}
                    >
                      <SelectTrigger className="rounded-xl">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_OPTIONS.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs text-slate-500">Priority</Label>
                    <Select
                      value={ticketDraft?.priority ?? 'medium'}
                      defaultValue={ticketDraft?.priority ?? 'medium'}
                      onValueChange={(v) =>
                        setTicketDraft((prev) => (prev ? { ...prev, priority: v as TicketPriority } : prev))
                      }
                      disabled={saving}
                    >
                      <SelectTrigger className="rounded-xl">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PRIORITY_OPTIONS.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p.toUpperCase()}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2 sm:col-span-2">
                    <Label className="text-xs text-slate-500">Assign owner</Label>
                    <Select
                      value={ticketDraft?.assignedTo ?? UNASSIGNED}
                      defaultValue={ticketDraft?.assignedTo ?? UNASSIGNED}
                      onValueChange={(v) =>
                        setTicketDraft((prev) => (prev ? { ...prev, assignedTo: v } : prev))
                      }
                      disabled={saving}
                    >
                      <SelectTrigger className="rounded-xl">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                        {assignees.map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {a.name} ({a.role})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="mt-4">
                  <Button type="button" className="rounded-full" disabled={saving || !ticketDraft} onClick={() => void applyTicketUpdate()}>
                    {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Save changes
                  </Button>
                </div>

                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Thread</p>
                  {msgLoading ? (
                    <p className="mt-2 text-sm text-slate-500">Loading messages...</p>
                  ) : (
                    <ul className="mt-2 max-h-48 space-y-2 overflow-y-auto text-sm">
                      {messages.length === 0 ? (
                        <li className="text-slate-500">No comments yet.</li>
                      ) : (
                        messages.map((m) => (
                          <li key={m.id} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-slate-700">
                            {m.message_text}
                            <span className="mt-1 block text-xs text-slate-400" data-testid="message-created-at">
                              {m.created_at ? new Date(m.created_at).toLocaleString() : '—'}
                            </span>
                          </li>
                        ))
                      )}
                    </ul>
                  )}
                </div>

                <div className="mt-4 space-y-2">
                  <Label className="text-xs text-slate-500">HR comment</Label>
                  <Textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Add an internal note or reply..."
                    className="min-h-[88px] rounded-xl"
                  />
                  <Button type="button" className="rounded-full" disabled={saving || !comment.trim()} onClick={() => void sendComment()}>
                    {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Post comment
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
