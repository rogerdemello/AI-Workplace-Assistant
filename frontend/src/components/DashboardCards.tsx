import { ShieldAlert, Ticket, TrendingUp, Users } from 'lucide-react';

interface DashboardCardsProps {
  engagementScore: number;
  riskLevel: 'Low' | 'Medium' | 'High';
  openTickets: number;
  enps?: number;
  attritionRisk?: number;
  activeUsers?: number;
}

const riskConfig = {
  Low:    { bar: 'metric-bar-positive', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  Medium: { bar: 'metric-bar-warning',  badge: 'bg-amber-50  text-amber-700  border-amber-200'  },
  High:   { bar: 'metric-bar-danger',   badge: 'bg-rose-50   text-rose-700   border-rose-200'   },
} as const;

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  barClass,
  badge,
}: {
  label: string;
  value: string | number;
  sub: string;
  icon: React.ElementType;
  barClass: string;
  badge?: string;
}) {
  return (
    <div className="card-hover relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
      {/* Accent bar top */}
      <div className={`absolute inset-x-0 top-0 h-1 ${barClass}`} />

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 pt-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
          {badge ? (
            <span className={`mt-2 inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold ${badge}`}>
              {value}
            </span>
          ) : (
            <p className="text-3xl font-bold text-slate-900">{value}</p>
          )}
          <p className="text-xs leading-5 text-slate-500">{sub}</p>
        </div>
        <div className="flex-shrink-0 rounded-2xl bg-slate-50 p-3 text-slate-500">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export function DashboardCards({
  engagementScore,
  riskLevel,
  openTickets,
  enps,
  attritionRisk,
  activeUsers,
}: DashboardCardsProps) {
  const { bar, badge } = riskConfig[riskLevel];

  const cards = [
    {
      label: 'Engagement Score',
      value: `${engagementScore}%`,
      sub: 'Resolution rate + active chat users',
      icon: TrendingUp,
      barClass: 'metric-bar-brand',
    },
    {
      label: 'Risk Level',
      value: riskLevel,
      sub: 'Based on sentiment and inactivity',
      icon: ShieldAlert,
      barClass: bar,
      badge,
    },
    {
      label: 'Open Tickets',
      value: openTickets,
      sub: 'Complaints, leave, and policy requests',
      icon: Ticket,
      barClass: openTickets > 10 ? 'metric-bar-danger' : 'metric-bar-brand',
    },
    ...(activeUsers !== undefined
      ? [{
          label: 'Active Users',
          value: activeUsers,
          sub: 'Employees chatted with Mark (30 days)',
          icon: Users,
          barClass: 'metric-bar-positive',
        }]
      : []),
    ...(enps !== undefined
      ? [{
          label: 'eNPS Proxy',
          value: enps > 0 ? `+${enps}` : `${enps}`,
          sub: 'Promoters minus detractors (30d)',
          icon: TrendingUp,
          barClass: enps >= 30 ? 'metric-bar-positive' : enps >= 0 ? 'metric-bar-warning' : 'metric-bar-danger',
        }]
      : []),
    ...(attritionRisk !== undefined
      ? [{
          label: 'Attrition Risk',
          value: `${attritionRisk}%`,
          sub: 'Employees with high risk score',
          icon: ShieldAlert,
          barClass: attritionRisk > 20 ? 'metric-bar-danger' : 'metric-bar-warning',
        }]
      : []),
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 animate-fade-up">
      {cards.map((c) => (
        <MetricCard key={c.label} {...(c as Parameters<typeof MetricCard>[0])} />
      ))}
    </div>
  );
}