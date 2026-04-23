"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, MessageSquareText, Users, CalendarCheck, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';
import { getLeaveRequests, approveLeave, rejectLeave, getTickets, type LeaveRequestResponse, type TicketResponse } from '@/lib/api';

const statusColors: Record<string, { bg: string; text: string }> = {
  open: { bg: 'bg-blue-100', text: 'text-blue-700' },
  in_progress: { bg: 'bg-amber-100', text: 'text-amber-700' },
  resolved: { bg: 'bg-green-100', text: 'text-green-700' },
  escalated: { bg: 'bg-red-100', text: 'text-red-700' },
  closed: { bg: 'bg-slate-100', text: 'text-slate-700' },
};

const priorityColors: Record<string, string> = {
  low: 'text-slate-500 bg-slate-100',
  medium: 'text-amber-600 bg-amber-100',
  high: 'text-orange-600 bg-orange-100',
  critical: 'text-red-600 bg-red-100',
};

export default function ManagerPage() {
  const router = useRouter();
  const { session, loading: authLoading, logout } = useAuth();
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequestResponse[]>([]);
  const [teamTickets, setTeamTickets] = useState<TicketResponse[]>([]);
  const [loadingLeave, setLoadingLeave] = useState(true);
  const [loadingTickets, setLoadingTickets] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (authLoading) return;

    if (!session) {
      router.replace('/login');
      return;
    }

    if (session.role !== 'manager') {
      if (session.role === 'hr' || session.role === 'admin') {
        router.replace('/dashboard');
      } else {
        router.replace('/employee');
      }
    }
  }, [authLoading, session, router]);

  useEffect(() => {
    async function fetchLeaveRequests() {
      setLoadingLeave(true);
      const pending = await getLeaveRequests('pending');
      setLeaveRequests(pending);
      setLoadingLeave(false);
    }

    async function fetchTeamTickets() {
      setLoadingTickets(true);
      const tickets = await getTickets();
      setTeamTickets(tickets);
      setLoadingTickets(false);
    }

    if (session?.role === 'manager') {
      fetchLeaveRequests();
      fetchTeamTickets();
    }
  }, [session, refreshKey]);

  const handleApproveLeave = async (leaveId: string) => {
    try {
      await approveLeave(leaveId);
      setLeaveRequests((prev) => prev.filter((r) => r.id !== leaveId));
    } catch (error) {
      console.error('Failed to approve leave:', error);
    }
  };

  const handleRejectLeave = async (leaveId: string) => {
    try {
      await rejectLeave(leaveId);
      setLeaveRequests((prev) => prev.filter((r) => r.id !== leaveId));
    } catch (error) {
      console.error('Failed to reject leave:', error);
    }
  };

  if (authLoading) {
    return <Spinner message="Verifying authentication..." />;
  }

  if (!session || session.role !== 'manager') {
    return <Spinner message="Verifying authentication..." />;
  }

  const pendingCount = leaveRequests.length;
  const openTicketsCount = teamTickets.filter((t) => t.status === 'open' || t.status === 'in_progress').length;

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <header className="flex flex-col gap-4 rounded-[2rem] border border-slate-200 bg-white px-6 py-5 shadow-sm lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600">Manager dashboard</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Team Control Center</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Manage your team&apos;s leave requests and track ticket assignments.
            </p>
          </div>

          <div className="flex gap-3">
            <Button variant="outline" className="rounded-full border-slate-200 bg-white" onClick={() => router.push('/employee')}>
              <MessageSquareText className="mr-2 h-4 w-4" />
              Employee view
            </Button>
            <Button
              className="rounded-full"
              onClick={() => {
                logout();
              }}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </header>

        <section className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <CalendarCheck className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Pending Leave</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{pendingCount}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                <AlertCircle className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Open Tickets</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{openTicketsCount}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-green-50 text-green-600">
                <Users className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Team Size</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">-</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                <MessageSquareText className="h-6 w-6" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Total Tickets</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{teamTickets.length}</p>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Pending Leave Requests</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingLeave ? (
                <div className="flex justify-center py-8">
                  <Spinner message="Loading leave requests..." />
                </div>
              ) : leaveRequests.length === 0 ? (
                <p className="text-sm text-slate-500">No pending leave requests</p>
              ) : (
                <div className="space-y-3">
                  {leaveRequests.map((request) => (
                    <div key={request.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <p className="font-medium text-slate-900">{request.employee_name}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            {request.leave_type || '—'} · {new Date(request.start_date).toLocaleDateString()} to {new Date(request.end_date).toLocaleDateString()}
                          </p>
                          {request.reason && <p className="mt-2 text-sm text-slate-600">{request.reason}</p>}
                        </div>
                        <div className="flex flex-col gap-2">
                          <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => handleApproveLeave(request.id)}>
                            Approve
                          </Button>
                          <Button size="sm" variant="outline" className="border-red-200 text-red-600 hover:bg-red-50" onClick={() => handleRejectLeave(request.id)}>
                            Reject
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Team Tickets</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingTickets ? (
                <div className="flex justify-center py-8">
                  <Spinner message="Loading tickets..." />
                </div>
              ) : teamTickets.length === 0 ? (
                <p className="text-sm text-slate-500">No tickets found</p>
              ) : (
                <div className="space-y-3">
                  {teamTickets.map((ticket) => (
                    <div key={ticket.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${priorityColors[ticket.priority]}`}>
                              {ticket.priority}
                            </span>
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[ticket.status]?.bg} ${statusColors[ticket.status]?.text}`}>
                              {ticket.status.replace('_', ' ')}
                            </span>
                          </div>
                          <p className="mt-2 font-medium text-slate-900">{ticket.query}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {ticket.category} · Created {new Date(ticket.created_at).toLocaleDateString()}
                          </p>
                          {ticket.assigned_to && <p className="mt-1 text-xs text-slate-500">Assigned to: {ticket.assigned_to}</p>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
