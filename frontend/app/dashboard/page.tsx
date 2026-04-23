"use client";

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, MessageSquareText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DashboardCards } from '@/components/DashboardCards';
import { SentimentChart } from '@/components/SentimentChart';
import { EmployeeTable } from '@/components/EmployeeTable';
import { EnpsGauge } from '@/components/EnpsGauge';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';
import { loadDashboardData, type DashboardData } from '@/lib/hr-data';
import { HrTicketManagement } from '@/components/HrTicketManagement';
import { HrAlertsCard } from '@/components/HrAlertsCard';
import { AppreciationCard } from '@/components/AppreciationCard';
import {
  approveLeave,
  getEmployeeScores,
  getHighRiskEmployees,
  getLeaveRequests,
  getWellbeingWeeklySummary,
  rejectLeave,
  type EmployeeScore,
  type EmployeeScoresResponse,
  type LeaveRequestResponse,
  type WellbeingHighRiskEmployee,
  type WellbeingWeeklySummary,
} from '@/lib/api';

export default function DashboardPage() {
  const router = useRouter();
  const { session, loading: authLoading, logout } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0);
  const [authChecked, setAuthChecked] = useState(false);
  const [authError, setAuthError] = useState(false);
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequestResponse[]>([]);
  const [leaveLoading, setLeaveLoading] = useState(false);
  const [highRiskRows, setHighRiskRows] = useState<WellbeingHighRiskEmployee[]>([]);
  const [weeklyWellbeing, setWeeklyWellbeing] = useState<WellbeingWeeklySummary | null>(null);
  const [wellbeingLoading, setWellbeingLoading] = useState(false);
  const [wellbeingError, setWellbeingError] = useState<string | null>(null);
  const [employeeScores, setEmployeeScores] = useState<EmployeeScoresResponse | null>(null);
  const [scoresLoading, setScoresLoading] = useState(false);
  const [scoresError, setScoresError] = useState<string | null>(null);

  const groupedTicketInsight = useMemo(() => {
    if (!data?.tickets?.length) return null;
    const groupCounts = new Map<string, number>();

    for (const ticket of data.tickets) {
      const issueTopic = (ticket.issue || '').split(/\s+/).slice(0, 4).join(' ').trim();
      const key = (ticket.against || issueTopic || 'general').toLowerCase();
      if (!key) continue;
      groupCounts.set(key, (groupCounts.get(key) ?? 0) + 1);
    }

    let topKey = '';
    let topCount = 0;
    for (const [key, count] of groupCounts.entries()) {
      if (count > topCount) {
        topKey = key;
        topCount = count;
      }
    }

    if (topCount < 3 || !topKey) return null;
    const readableTopic = topKey.replace(/\b\w/g, (ch) => ch.toUpperCase());
    return `Multiple complaints about ${readableTopic} (${topCount} tickets).`;
  }, [data?.tickets]);

  useEffect(() => {
    if (authLoading) return;
    if (authChecked) return;
    setAuthChecked(true);

    const timeout = setTimeout(() => setAuthError(true), 3000);

    if (!session) {
      clearTimeout(timeout);
      router.replace('/login');
      return;
    }

    if (session.role === 'employee') {
      clearTimeout(timeout);
      router.replace('/employee');
      return;
    }

    clearTimeout(timeout);
  }, [authLoading, authChecked, session, router]);

  useEffect(() => {
    if (authLoading) return;
    if (!session || session.role === 'employee') return;

    const run = async () => {
      setLoading(true);
      const dashboardData = await loadDashboardData();
      setData(dashboardData);
      setLoading(false);
    };

    void run();
  }, [authLoading, session, dashboardRefreshKey]);

  useEffect(() => {
    const fetchLeaveRequests = async () => {
      setLeaveLoading(true);
      const pendingRequests = await getLeaveRequests('pending');
      setLeaveRequests(pendingRequests);
      setLeaveLoading(false);
    };

    if (session?.role === 'hr' || session?.role === 'admin') {
      fetchLeaveRequests();
    }
  }, [session, dashboardRefreshKey]);

  useEffect(() => {
    if (!(session?.role === 'hr' || session?.role === 'admin')) return;
    const timer = window.setInterval(() => {
      setDashboardRefreshKey((key) => key + 1);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [session]);

  useEffect(() => {
    const fetchWellbeingInsights = async () => {
      setWellbeingLoading(true);
      setWellbeingError(null);
      try {
        const [weekly, highRisk] = await Promise.all([
          getWellbeingWeeklySummary(),
          getHighRiskEmployees(8),
        ]);
        setWeeklyWellbeing(weekly);
        setHighRiskRows(highRisk);
      } catch (error) {
        setWellbeingError(error instanceof Error ? error.message : 'Failed to load wellbeing insights');
        setWeeklyWellbeing(null);
        setHighRiskRows([]);
      } finally {
        setWellbeingLoading(false);
      }
    };

    if (session?.role === 'hr' || session?.role === 'admin') {
      fetchWellbeingInsights();
    }
  }, [session, dashboardRefreshKey]);

  useEffect(() => {
    const fetchEmployeeScores = async () => {
      setScoresLoading(true);
      setScoresError(null);
      try {
        const scores = await getEmployeeScores(25, true);
        setEmployeeScores(scores);
      } catch (error) {
        setScoresError(error instanceof Error ? error.message : 'Failed to load employee scores');
        setEmployeeScores(null);
      } finally {
        setScoresLoading(false);
      }
    };

    if (session?.role === 'hr' || session?.role === 'admin') {
      fetchEmployeeScores();
    }
  }, [session, dashboardRefreshKey]);

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

  if (authError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-lg font-semibold text-rose-600">Authentication timed out</p>
          <p className="mt-2 text-sm text-slate-500">Please refresh the page or sign in again.</p>
        </div>
      </div>
    );
  }

  if (authLoading) {
    return <Spinner message="Verifying authentication..." />;
  }
  if (!session) {
    return null;
  }
  if (loading || !data) {
    return <Spinner message="Verifying authentication..." />;
  }

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <header className="flex flex-col gap-4 rounded-[2rem] border border-slate-200 bg-white px-6 py-5 shadow-sm lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600">HR dashboard</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Mark control center</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">Tickets, sentiment, and employee insight all flow here from the employee chat experience.</p>
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
                router.push('/login');
              }}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </header>

        <DashboardCards
          engagementScore={data.metrics.engagementScore}
          riskLevel={data.metrics.riskLevel}
          openTickets={data.metrics.openTickets}
          enps={data.metrics.enps}
          attritionRisk={data.metrics.attritionRiskPct}
          activeUsers={data.metrics.activeUsers}
        />

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          {data.sentimentPoints.length > 0 ? (
            <SentimentChart data={data.sentimentPoints} />
          ) : (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle>Sentiment Over Time</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-slate-500">No sentiment data available.</p>
              </CardContent>
            </Card>
          )}

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>AI Insight + eNPS</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl bg-blue-50 p-4 text-sm leading-7 text-blue-900">
                {data.metrics.aiSummary}
              </div>
              <div className="flex flex-col items-center justify-center py-4">
                <EnpsGauge enps={data.metrics.enps ?? 0} size={180} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Total tickets</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{data.metrics.totalTickets}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Departments in view</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{data.metrics.departmentsInView}</p>
                </div>
              </div>
              {/* Department Breakdown */}
              {data.departmentBreakdown && data.departmentBreakdown.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Dept Sentiment</p>
                  {data.departmentBreakdown.map((d) => (
                    <div key={d.department} className="flex items-center gap-3">
                      <span className="w-24 truncate text-xs text-slate-600">{d.department}</span>
                      <div className="flex flex-1 h-2 rounded-full overflow-hidden bg-slate-100">
                        <div className="bg-emerald-400" style={{ width: `${d.positive}%` }} />
                        <div className="bg-amber-300"  style={{ width: `${d.neutral}%`  }} />
                        <div className="bg-rose-400"   style={{ width: `${d.negative}%` }} />
                      </div>
                      <span className={`text-xs font-bold ${
                        d.score >= 20 ? 'text-emerald-600' : d.score >= 0 ? 'text-amber-500' : 'text-rose-500'
                      }`}>{d.score > 0 ? `+${d.score}` : d.score}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Weekly quality ({data.weeklyQuality.windowDays}d)
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-slate-500">Average CSAT</p>
                    <p className="text-xl font-semibold text-slate-900">{data.weeklyQuality.avgCsat.toFixed(2)} / 5</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Helpful rate</p>
                    <p className="text-xl font-semibold text-slate-900">{data.weeklyQuality.helpfulRate.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Avg first response</p>
                    <p className="text-xl font-semibold text-slate-900">{data.weeklyQuality.avgFirstResponseSeconds.toFixed(1)}s</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Quality label</p>
                    <p className="text-sm font-semibold text-slate-900">{data.weeklyQuality.qualityLabel}</p>
                    <p className="text-xs text-slate-500">{data.weeklyQuality.feedbackResponses} feedback responses</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <HrAlertsCard />

        <AppreciationCard />

        {groupedTicketInsight ? (
          <Card className="border-rose-200 bg-rose-50/70 shadow-sm">
            <CardContent className="py-4">
              <p className="text-sm font-medium text-rose-900">{groupedTicketInsight}</p>
            </CardContent>
          </Card>
        ) : null}

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle>Wellbeing intelligence</CardTitle>
          </CardHeader>
          <CardContent>
            {wellbeingLoading ? (
              <p className="text-sm text-slate-500">Loading wellbeing insights...</p>
            ) : wellbeingError ? (
              <p className="text-sm text-rose-600">{wellbeingError}</p>
            ) : !weeklyWellbeing ? (
              <p className="text-sm text-slate-500">No wellbeing insight available yet.</p>
            ) : (
              <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Window</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900">{weeklyWellbeing.window_days} days</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">High risk employees</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900">{weeklyWellbeing.high_risk_employees}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Follow-up signals</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900">{weeklyWellbeing.followup_signals}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Avg engagement score</p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900">{weeklyWellbeing.avg_engagement_score.toFixed(1)}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Current high-risk employees</p>
                  {highRiskRows.length === 0 ? (
                    <p className="text-sm text-slate-500">No high-risk employees detected right now.</p>
                  ) : (
                    highRiskRows.map((row) => (
                      <div key={row.user_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-slate-900">{row.name}</p>
                            <p className="text-xs uppercase tracking-wide text-slate-400">{row.risk_level} risk · mood {row.mood_score.toFixed(1)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-semibold text-slate-900">{row.risk_score.toFixed(1)}</p>
                            <p className="text-xs text-slate-500">risk score</p>
                          </div>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">Open tickets: {row.open_tickets} · Last active: {row.last_active}</p>
                        {row.reasons.length > 0 ? (
                          <p className="mt-2 text-sm text-slate-600">{row.reasons[0]}</p>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {(session?.role === 'hr' || session?.role === 'admin') && (
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Mental health scores</CardTitle>
            </CardHeader>
            <CardContent>
              {scoresLoading ? (
                <p className="text-sm text-slate-500">Loading mental health scores...</p>
              ) : scoresError ? (
                <p className="text-sm text-rose-600">{scoresError}</p>
              ) : !employeeScores ? (
                <p className="text-sm text-slate-500">No mental health data available yet.</p>
              ) : (
                <div className="space-y-6">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Org average</p>
                      <p className="mt-2 text-3xl font-bold text-slate-900">{employeeScores.org_average}</p>
                      <p className="text-xs text-slate-500">out of 100</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Employees assessed</p>
                      <p className="mt-2 text-3xl font-bold text-slate-900">{employeeScores.scores.length}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Risk alerts</p>
                      <p className="mt-2 text-3xl font-bold text-slate-900">{employeeScores.risk_alerts.length}</p>
                    </div>
                  </div>

                  {employeeScores.risk_alerts.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Risk alerts</p>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {employeeScores.risk_alerts.map((alert) => (
                          <div
                            key={alert.user_id}
                            className={`rounded-2xl border p-4 shadow-sm ${
                              alert.status === 'critical'
                                ? 'border-rose-200 bg-rose-50'
                                : alert.status === 'struggling'
                                ? 'border-amber-200 bg-amber-50'
                                : 'border-slate-200 bg-white'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium text-slate-900">{alert.name}</p>
                                <p className="text-xs uppercase tracking-wide text-slate-400">{alert.status.replace('_', ' ')}</p>
                              </div>
                              <div className="text-right">
                                <p className="text-lg font-semibold text-slate-900">{alert.mental_health}</p>
                                <p className="text-xs text-slate-500">score</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Employee health cards</p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {employeeScores.scores.slice(0, 9).map((score) => {
                        const statusColor =
                          score.status === 'healthy'
                            ? 'bg-emerald-100 text-emerald-700'
                            : score.status === 'stable'
                            ? 'bg-blue-100 text-blue-700'
                            : score.status === 'at_risk'
                            ? 'bg-amber-100 text-amber-700'
                            : score.status === 'struggling'
                            ? 'bg-orange-100 text-orange-700'
                            : 'bg-rose-100 text-rose-700';
                        return (
                          <div key={score.user_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="truncate font-medium text-slate-900">{score.name}</p>
                                <p className="truncate text-xs text-slate-500">{score.department || 'No department'}</p>
                              </div>
                              <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${statusColor}`}>
                                {score.mental_health}
                              </span>
                            </div>
                            <div className="mt-3 flex items-center justify-between text-xs">
                              <span className="text-slate-500">Sentiment: {score.sentiment}</span>
                              <span className="text-slate-500">Engagement: {score.engagement}</span>
                            </div>
                            <div className="mt-2 h-2 rounded-full bg-slate-100">
                              <div
                                className={`h-2 rounded-full ${
                                  score.mental_health >= 80
                                    ? 'bg-emerald-500'
                                    : score.mental_health >= 60
                                    ? 'bg-blue-500'
                                    : score.mental_health >= 40
                                    ? 'bg-amber-500'
                                    : 'bg-rose-500'
                                }`}
                                style={{ width: `${score.mental_health}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {(session?.role === 'hr' || session?.role === 'admin') && (
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Pending Approvals</CardTitle>
            </CardHeader>
            <CardContent>
              {leaveLoading ? (
                <p className="text-sm text-slate-500">Loading leave requests...</p>
              ) : leaveRequests.length === 0 ? (
                <p className="text-sm text-slate-500">No pending leave requests</p>
              ) : (
                <div className="space-y-3">
                  {leaveRequests.map((request) => (
                    <div key={request.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-slate-900">{request.employee_name}</p>
                          <p className="text-sm text-slate-500">
                            {request.leave_type || '—'} · {request.start_date} to {request.end_date}
                          </p>
                          {request.reason && (
                            <p className="mt-1 text-sm text-slate-600">{request.reason}</p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-200 text-red-600 hover:bg-red-50"
                            onClick={() => handleRejectLeave(request.id)}
                          >
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            className="bg-green-600 hover:bg-green-700"
                            onClick={() => handleApproveLeave(request.id)}
                          >
                            Approve
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <section className="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Ticket Management</CardTitle>
            </CardHeader>
            <CardContent>
              <HrTicketManagement
                initialRows={data.tickets}
                onTicketsChanged={() => setDashboardRefreshKey((k) => k + 1)}
              />
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Employee insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                Employee sentiment is computed from live message activity and rolled into risk scoring for HR review.
              </div>
              {data.employees.length === 0 ? (
                <p className="text-sm text-slate-500">No employee data available.</p>
              ) : (
                <div className="grid gap-3">
                  {data.employees.slice(0, 3).map((employee) => (
                    <div key={employee.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-slate-900">{employee.name}</p>
                          <p className="text-sm text-slate-500">{employee.employeeId} · {employee.department || '—'}</p>
                        </div>
                        <div className="text-right text-sm">
                          <p className="font-semibold text-slate-900">{employee.sentimentScore}%</p>
                          <p className="text-slate-500">sentiment</p>
                        </div>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-slate-100">
                        <div className="h-2 rounded-full bg-blue-600" style={{ width: `${employee.sentimentScore}%` }} />
                      </div>
                      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                        <span>Risk score: {employee.riskScore}</span>
                        <span>{employee.lastActive}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600">Employee table</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Search and filter employee risk</h2>
          </div>
          <EmployeeTable rows={data.employees} />
        </section>
      </div>
    </div>
  );
}
