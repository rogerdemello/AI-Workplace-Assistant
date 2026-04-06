"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BarChart3, LogOut, MessageSquareText, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DashboardCards } from '@/components/DashboardCards';
import { SentimentChart } from '@/components/SentimentChart';
import { EmployeeTable } from '@/components/EmployeeTable';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';
import { clearSession } from '@/lib/session';
import { loadDashboardData, type DashboardData } from '@/lib/hr-data';

export default function DashboardPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    if (session?.role === 'employee') {
      router.replace('/employee');
      return;
    }

    const run = async () => {
      setLoading(true);
      const dashboardData = await loadDashboardData();
      setData(dashboardData);
      setLoading(false);
    };

    void run();
  }, [authLoading, session, router]);

  if (authLoading || loading || !data) {
    return <Spinner message="Verifying authentication..." />;
  }

  const statusStyles = {
    Open: 'bg-blue-50 text-blue-700 border-blue-200',
    'In Review': 'bg-amber-50 text-amber-700 border-amber-200',
    Resolved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    Escalated: 'bg-rose-50 text-rose-700 border-rose-200',
  } as const;

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
                clearSession();
                router.replace('/login?role=hr');
              }}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </header>

        <DashboardCards engagementScore={data.metrics.engagementScore} riskLevel={data.metrics.riskLevel} openTickets={data.metrics.openTickets} />

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <SentimentChart data={data.sentimentPoints} />

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>AI Insight</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl bg-blue-50 p-4 text-sm leading-7 text-blue-900">
                {data.metrics.aiSummary}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Total tickets</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{data.metrics.totalTickets}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Departments in view</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">4</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle>Ticket Management</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="py-3 pr-4 font-semibold">Employee ID</th>
                      <th className="py-3 pr-4 font-semibold">Issue</th>
                      <th className="py-3 pr-4 font-semibold">Against</th>
                      <th className="py-3 pr-4 font-semibold">Status</th>
                      <th className="py-3 font-semibold">Anonymous</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.tickets.map((ticket) => (
                      <tr key={ticket.id} className="hover:bg-slate-50">
                        <td className="py-4 pr-4 font-medium text-slate-900">{ticket.employeeId}</td>
                        <td className="py-4 pr-4 text-slate-600">{ticket.issue}</td>
                        <td className="py-4 pr-4 text-slate-600">{ticket.against}</td>
                        <td className="py-4 pr-4">
                          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[ticket.status]}`}>
                            {ticket.status}
                          </span>
                        </td>
                        <td className="py-4 text-slate-600">{ticket.anonymous ? 'Yes' : 'No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
              <div className="grid gap-3">
                {data.employees.slice(0, 3).map((employee) => (
                  <div key={employee.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium text-slate-900">{employee.name}</p>
                        <p className="text-sm text-slate-500">{employee.employeeId} · {employee.department}</p>
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
