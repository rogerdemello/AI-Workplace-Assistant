import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ShieldAlert, Ticket, TrendingUp } from 'lucide-react';

interface DashboardCardsProps {
  engagementScore: number;
  riskLevel: 'Low' | 'Medium' | 'High';
  openTickets: number;
}

export function DashboardCards({ engagementScore, riskLevel, openTickets }: DashboardCardsProps) {
  const riskStyles = {
    Low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    Medium: 'bg-amber-50 text-amber-700 border-amber-200',
    High: 'bg-rose-50 text-rose-700 border-rose-200',
  } as const;

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-slate-500">Engagement Score</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end justify-between">
          <div>
            <p className="text-3xl font-semibold text-slate-900">{engagementScore}%</p>
            <p className="mt-2 text-sm text-emerald-600">+4.2% from last week</p>
          </div>
          <div className="rounded-2xl bg-blue-50 p-3 text-blue-600">
            <TrendingUp className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-slate-500">Risk Level</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end justify-between">
          <div>
            <p className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold ${riskStyles[riskLevel]}`}>{riskLevel}</p>
            <p className="mt-2 text-sm text-slate-500">Based on employee sentiment and inactivity</p>
          </div>
          <div className="rounded-2xl bg-amber-50 p-3 text-amber-600">
            <ShieldAlert className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-slate-500">Open Tickets</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end justify-between">
          <div>
            <p className="text-3xl font-semibold text-slate-900">{openTickets}</p>
            <p className="mt-2 text-sm text-slate-500">Complaints, leave, and policy requests</p>
          </div>
          <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
            <Ticket className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}