import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { getKpisWithDeltas, type KpiMetric, type KpisWithDeltas } from "@/lib/api/dashboard";

interface TileDef {
  key: keyof KpisWithDeltas["metrics"];
  label: string;
  format: (m: KpiMetric) => string;
  // For "higher = better" metrics (sentiment, active employees, resolved
  // tickets) a positive delta is good. For new_tickets and at_risk_count a
  // positive delta is bad. This drives the colour of the delta chip.
  positiveIsGood: boolean;
  help: string;
}

const TILES: TileDef[] = [
  {
    key: "avg_sentiment",
    label: "Avg sentiment",
    format: (m) => (m.current == null ? "—" : `${Math.round(m.current)}`),
    positiveIsGood: true,
    help: "Mean sentiment score (0–100) across logged messages in the window.",
  },
  {
    key: "active_employees",
    label: "Active employees",
    format: (m) => (m.current == null ? "—" : String(m.current)),
    positiveIsGood: true,
    help: "Distinct employees who sent a chat message in the window.",
  },
  {
    key: "new_tickets",
    label: "New tickets",
    format: (m) => (m.current == null ? "—" : String(m.current)),
    positiveIsGood: false,
    help: "Tickets opened in the window. A spike here usually deserves attention.",
  },
  {
    key: "resolved_tickets",
    label: "Resolved tickets",
    format: (m) => (m.current == null ? "—" : String(m.current)),
    positiveIsGood: true,
    help: "Tickets moved to resolved or closed in the window.",
  },
  {
    key: "at_risk_count",
    label: "At-risk employees",
    format: (m) => (m.current == null ? "—" : String(m.current)),
    positiveIsGood: false,
    help: "Employees with a current risk score ≥ 70. Snapshot, not flow.",
  },
];

const RANGE_OPTIONS = [
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
  { days: 90, label: "90d" },
];

export function KpiStatsRow() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<KpisWithDeltas | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getKpisWithDeltas(days).then((d) => {
      if (!cancelled) {
        setData(d);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [days]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Headline metrics</div>
          <div className="text-sm font-medium mt-0.5">vs prior {days}-day window</div>
        </div>
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
              onClick={() => setDays(opt.days)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-md transition-colors",
                days === opt.days
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {TILES.map((tile, i) => {
          const metric = data?.metrics[tile.key];
          return (
            <motion.div
              key={tile.key}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.04 }}
              className="rounded-2xl border border-border bg-card p-4 flex flex-col gap-2"
              title={tile.help}
            >
              <div className="text-xs text-muted-foreground">{tile.label}</div>
              <div className="font-display text-2xl tracking-tight">
                {loading ? "…" : metric ? tile.format(metric) : "—"}
              </div>
              <DeltaChip metric={metric} positiveIsGood={tile.positiveIsGood} loading={loading} />
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function DeltaChip({
  metric,
  positiveIsGood,
  loading,
}: {
  metric?: KpiMetric;
  positiveIsGood: boolean;
  loading: boolean;
}) {
  if (loading) {
    return <div className="text-[11px] text-muted-foreground">…</div>;
  }
  if (!metric || metric.delta == null) {
    return <div className="text-[11px] text-muted-foreground">no prior data</div>;
  }
  const delta = metric.delta;
  if (delta === 0) {
    return (
      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Minus className="size-3" /> no change
      </div>
    );
  }
  const direction = delta > 0 ? "up" : "down";
  const good = (delta > 0 && positiveIsGood) || (delta < 0 && !positiveIsGood);
  const Icon = direction === "up" ? ArrowUpRight : ArrowDownRight;
  return (
    <div
      className={cn(
        "flex items-center gap-1 text-[11px] font-medium",
        good ? "text-emerald" : "text-danger",
      )}
    >
      <Icon className="size-3" />
      {delta > 0 ? "+" : ""}
      {Number.isInteger(delta) ? delta : delta.toFixed(1)} vs prior
    </div>
  );
}
