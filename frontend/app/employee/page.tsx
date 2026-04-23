"use client";

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LogOut } from 'lucide-react';
import { ChatPanel } from '@/components/ChatPanel';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';
import {
  cancelLeave,
  cancelWellbeingReminder,
  getLeaveRequests,
  getTickets,
  getWellbeingReminders,
  getWellbeingWeeklySummary,
  updateWellbeingReminder,
  type LeaveRequestResponse,
  type LeaveStatus,
  type TicketResponse,
  type TicketStatus,
  type TicketPriority,
  type WellbeingReminderResponse,
  type WellbeingWeeklySummary,
} from '@/lib/api';

const leaveStatusColors: Record<LeaveStatus, { bg: string; text: string }> = {
  pending: { bg: 'bg-amber-100', text: 'text-amber-700' },
  approved: { bg: 'bg-green-100', text: 'text-green-700' },
  rejected: { bg: 'bg-red-100', text: 'text-red-700' },
  cancelled: { bg: 'bg-slate-100', text: 'text-slate-700' },
};

const ticketStatusColors: Record<TicketStatus, { bg: string; text: string }> = {
  open: { bg: 'bg-blue-100', text: 'text-blue-700' },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-700' },
  resolved: { bg: 'bg-green-100', text: 'text-green-700' },
  escalated: { bg: 'bg-rose-100', text: 'text-rose-700' },
  closed: { bg: 'bg-slate-100', text: 'text-slate-700' },
};

const ticketPriorityColors: Record<TicketPriority, { bg: string; text: string }> = {
  low: { bg: 'bg-slate-100', text: 'text-slate-700' },
  medium: { bg: 'bg-blue-100', text: 'text-blue-700' },
  high: { bg: 'bg-amber-100', text: 'text-amber-700' },
  critical: { bg: 'bg-rose-100', text: 'text-rose-700' },
};

function WidgetSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 w-full animate-pulse rounded bg-slate-100" />
      ))}
    </div>
  );
}

function truncate(str: string, max: number) {
  if (str.length <= max) return str;
  return str.slice(0, max) + '…';
}

function getMoodEmoji(score: number) {
  if (score >= 80) return '😊';
  if (score >= 60) return '🙂';
  if (score >= 40) return '😐';
  if (score >= 20) return '😟';
  return '😢';
}

function formatMoodScore(score: number) {
  const normalized = score <= 1 ? score * 100 : score;
  return `${Math.round(normalized)}%`;
}

export default function EmployeePage() {
  const router = useRouter();
  const { session, loading: authLoading, logout } = useAuth();
  const { showToast } = useToast();

  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [loadingTickets, setLoadingTickets] = useState(true);

  const [leaveRequests, setLeaveRequests] = useState<LeaveRequestResponse[]>([]);
  const [loadingLeave, setLoadingLeave] = useState(true);
  const [cancellingLeaveId, setCancellingLeaveId] = useState<string | null>(null);

  const [reminders, setReminders] = useState<WellbeingReminderResponse[]>([]);
  const [loadingReminders, setLoadingReminders] = useState(true);
  const [remindersError, setRemindersError] = useState(false);

  const [wellbeingSummary, setWellbeingSummary] = useState<WellbeingWeeklySummary | null>(null);
  const [loadingMood, setLoadingMood] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace('/login');
      return;
    }
    if (session.role === 'hr' || session.role === 'admin') {
      router.replace('/dashboard');
      return;
    }
    if (session.role === 'manager') {
      router.replace('/manager');
    }
  }, [authLoading, session, router]);

  useEffect(() => {
    async function fetchTickets() {
      if (!session) return;
      try {
        const data = await getTickets();
        setTickets(data);
      } catch (error) {
        console.error('Failed to fetch tickets:', error);
      } finally {
        setLoadingTickets(false);
      }
    }
    if (session) fetchTickets();
  }, [session]);

  useEffect(() => {
    async function fetchLeaveRequests() {
      if (!session) return;
      try {
        const requests = await getLeaveRequests();
        setLeaveRequests(requests);
      } catch (error) {
        console.error('Failed to fetch leave requests:', error);
      } finally {
        setLoadingLeave(false);
      }
    }
    if (session) fetchLeaveRequests();
  }, [session]);

  const loadReminders = useCallback(async () => {
    if (!session) return;
    try {
      setLoadingReminders(true);
      setRemindersError(false);
      const rows = await getWellbeingReminders(false);
      setReminders(rows);
    } catch (error) {
      setRemindersError(true);
      console.error('Failed to load reminders:', error);
    } finally {
      setLoadingReminders(false);
    }
  }, [session]);

  useEffect(() => {
    if (!session) return;
    void loadReminders();
  }, [session, loadReminders]);

  useEffect(() => {
    const onReminderUpdated = () => void loadReminders();
    if (typeof window !== 'undefined') {
      window.addEventListener('mark:reminders-updated', onReminderUpdated);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('mark:reminders-updated', onReminderUpdated);
      }
    };
  }, [loadReminders]);

  useEffect(() => {
    async function fetchMood() {
      if (!session) return;
      setLoadingMood(true);
      try {
        const summary = await getWellbeingWeeklySummary();
        setWellbeingSummary(summary);
      } catch (error) {
        console.error('Failed to load mood data:', error);
      } finally {
        setLoadingMood(false);
      }
    }
    if (session) fetchMood();
  }, [session]);

  const handleCancelLeave = async (leaveId: string) => {
    try {
      setCancellingLeaveId(leaveId);
      const updated = await cancelLeave(leaveId);
      setLeaveRequests((current) => current.map((r) => (r.id === leaveId ? updated : r)));
      showToast({
        title: 'Leave request cancelled',
        description: 'Your pending leave request has been cancelled.',
        variant: 'info',
      });
    } catch (error) {
      showToast({
        title: 'Could not cancel leave request',
        description: error instanceof Error ? error.message : 'Please try again shortly.',
        variant: 'error',
      });
    } finally {
      setCancellingLeaveId(null);
    }
  };

  const handlePauseResumeReminder = async (reminder: WellbeingReminderResponse) => {
    const nextStatus = reminder.status === 'active' ? 'paused' : 'active';
    try {
      const updated = await updateWellbeingReminder(reminder.id, { status: nextStatus });
      setReminders((current) => current.map((r) => (r.id === updated.id ? updated : r)));
      showToast({
        title: nextStatus === 'paused' ? 'Reminder paused' : 'Reminder resumed',
        description: `${updated.title} is now ${nextStatus}.`,
        variant: 'info',
      });
    } catch (error) {
      showToast({
        title: 'Reminder update failed',
        description: error instanceof Error ? error.message : 'Please try again.',
        variant: 'error',
      });
    }
  };

  const handleCancelReminder = async (reminderId: string) => {
    try {
      const target = reminders.find((r) => r.id === reminderId);
      await cancelWellbeingReminder(reminderId);
      setReminders((current) => current.filter((r) => r.id !== reminderId));
      showToast({
        title: 'Reminder cancelled',
        description: target ? `${target.title} has been cancelled.` : 'Reminder has been cancelled.',
        variant: 'info',
      });
    } catch (error) {
      showToast({
        title: 'Cancel failed',
        description: error instanceof Error ? error.message : 'Please try again.',
        variant: 'error',
      });
    }
  };

  if (authLoading) {
    return <Spinner message="Verifying authentication..." />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#eff6ff,transparent_34%),linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-blue-600">Employee</span>
          <Button
            variant="outline"
            size="sm"
            className="rounded-full border-slate-200 bg-white text-slate-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
            onClick={() => { logout(); router.push('/login'); }}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
        </div>

        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900 md:text-4xl">My Dashboard</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">Everything you need in one place.</p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Card data-testid="my-tickets-widget" className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
            <CardHeader>
              <CardTitle className="text-xl">My Tickets</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingTickets ? (
                <WidgetSkeleton rows={3} />
              ) : tickets.length === 0 ? (
                <p className="text-sm text-slate-500">No tickets yet</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                        <th className="pb-2 pr-4">Issue</th>
                        <th className="pb-2 pr-4">Status</th>
                        <th className="pb-2">Priority</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {tickets.map((ticket) => (
                        <tr key={ticket.id}>
                          <td className="py-3 pr-4 text-slate-700 max-w-[200px] truncate" title={ticket.query}>
                            {truncate(ticket.query, 40)}
                          </td>
                          <td className="py-3 pr-4">
                            <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${ticketStatusColors[ticket.status].bg} ${ticketStatusColors[ticket.status].text}`}>
                              {ticket.status.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="py-3">
                            <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${ticketPriorityColors[ticket.priority].bg} ${ticketPriorityColors[ticket.priority].text}`}>
                              {ticket.priority}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="my-leaves-widget" className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
            <CardHeader>
              <CardTitle className="text-xl">My Leaves</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingLeave ? (
                <WidgetSkeleton rows={3} />
              ) : leaveRequests.length === 0 ? (
                <p className="text-sm text-slate-500">No leave requests</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                        <th className="pb-2 pr-4">Dates</th>
                        <th className="pb-2 pr-4">Type</th>
                        <th className="pb-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {leaveRequests.map((request) => (
                        <tr key={request.id}>
                          <td className="py-3 pr-4 text-slate-700 whitespace-nowrap">
                            {new Date(request.start_date).toLocaleDateString()} – {new Date(request.end_date).toLocaleDateString()}
                          </td>
                          <td className="py-3 pr-4 text-slate-700 capitalize">
                            {(request.leave_type || '—').replace(/_/g, ' ')}
                          </td>
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${leaveStatusColors[request.status || 'pending'].bg} ${leaveStatusColors[request.status || 'pending'].text}`}>
                                {request.status || 'Pending'}
                              </span>
                              {request.status === 'pending' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="rounded-full border-rose-200 text-rose-600 hover:bg-rose-50 h-7 px-2 text-xs"
                                  disabled={cancellingLeaveId === request.id}
                                  onClick={() => void handleCancelLeave(request.id)}
                                >
                                  Cancel
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="my-reminders-widget" className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
            <CardHeader>
              <CardTitle className="text-xl">My Reminders</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingReminders ? (
                <WidgetSkeleton rows={3} />
              ) : remindersError ? (
                <p className="text-sm text-slate-500">Reminders appear here</p>
              ) : reminders.length === 0 ? (
                <p className="text-sm text-slate-500">Reminders appear here</p>
              ) : (
                <div className="space-y-3">
                  {reminders.map((reminder) => (
                    <div key={reminder.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-slate-900">{reminder.title}</p>
                          <p className="text-sm text-slate-600">{reminder.message}</p>
                          <p className="mt-1 text-xs text-slate-400">
                            Next: {reminder.next_trigger_at ? new Date(reminder.next_trigger_at).toLocaleString() : 'Not scheduled'}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full h-7 px-2 text-xs"
                            onClick={() => void handlePauseResumeReminder(reminder)}
                          >
                            {reminder.status === 'active' ? 'Pause' : 'Resume'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full border-rose-200 text-rose-600 hover:bg-rose-50 h-7 px-2 text-xs"
                            onClick={() => void handleCancelReminder(reminder.id)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="mood-snapshot-widget" className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
            <CardHeader>
              <CardTitle className="text-xl">Mood Snapshot</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingMood ? (
                <WidgetSkeleton rows={2} />
              ) : !wellbeingSummary ? (
                <p className="text-sm text-slate-500">No mood data available</p>
              ) : (
                <div className="flex items-center gap-6">
                  <span className="text-5xl" aria-hidden="true">
                    {getMoodEmoji(wellbeingSummary.avg_engagement_score)}
                  </span>
                  <div>
                    <p className="text-3xl font-bold text-slate-900">
                      {formatMoodScore(wellbeingSummary.avg_engagement_score)}
                    </p>
                    <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                      Avg Engagement Score
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      <ChatPanel key={session?.email ?? 'guest'} />
    </div>
  );
}
