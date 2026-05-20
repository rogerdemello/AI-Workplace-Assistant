import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { getDepartmentsHeatmap, type DepartmentHeatmapRow } from "@/lib/api/dashboard";

type BucketKey = "positive" | "watch" | "at_risk";

const BUCKETS: { key: BucketKey; label: string; tone: string }[] = [
  { key: "positive", label: "Positive", tone: "bg-emerald-soft text-emerald" },
  { key: "watch", label: "Watch", tone: "bg-warning-soft text-warning" },
  { key: "at_risk", label: "At-risk", tone: "bg-danger-soft text-danger" },
];

export function DepartmentHeatmapCard() {
  const [rows, setRows] = useState<DepartmentHeatmapRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getDepartmentsHeatmap().then((data) => {
      if (cancelled) return;
      setRows(data?.departments ?? []);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxPerBucket: Record<BucketKey, number> = {
    positive: Math.max(1, ...rows.map((r) => r.positive)),
    watch: Math.max(1, ...rows.map((r) => r.watch)),
    at_risk: Math.max(1, ...rows.map((r) => r.at_risk)),
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Department heatmap</div>
          <div className="text-sm font-medium mt-0.5">Sentiment distribution across teams</div>
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-sm text-muted-foreground">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No department data yet. Add employees with department assignments to populate this view.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="text-left font-medium pb-2">Department</th>
                {BUCKETS.map((b) => (
                  <th key={b.key} className="text-center font-medium pb-2 px-2">
                    {b.label}
                  </th>
                ))}
                <th className="text-center font-medium pb-2 px-2">Total</th>
                <th className="text-right font-medium pb-2 px-2">Avg score</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.department_id ?? row.department_name} className="border-t border-border/60">
                  <td className="py-2 pr-3 font-medium">{row.department_name}</td>
                  {BUCKETS.map((b) => {
                    const value = row[b.key];
                    const max = maxPerBucket[b.key];
                    const intensity = max === 0 ? 0 : value / max;
                    return (
                      <td key={b.key} className="px-2 py-2 text-center">
                        <HeatCell value={value} intensity={intensity} tone={b.tone} />
                      </td>
                    );
                  })}
                  <td className="px-2 py-2 text-center text-muted-foreground">{row.total}</td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {row.avg_sentiment == null ? "—" : Math.round(row.avg_sentiment)}
                  </td>
                  <td className="pl-2 py-2 text-right">
                    {row.department_id ? (
                      <Link
                        to={`/employees?departmentId=${row.department_id}`}
                        className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        Open <ArrowUpRight className="size-3" />
                      </Link>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HeatCell({ value, intensity, tone }: { value: number; intensity: number; tone: string }) {
  // Map intensity 0..1 to a 4-step opacity ramp so empty cells are visibly distinct.
  const step = intensity === 0 ? 0 : intensity < 0.34 ? 1 : intensity < 0.67 ? 2 : 3;
  const ramp = ["opacity-30", "opacity-60", "opacity-80", "opacity-100"];
  return (
    <span
      className={cn(
        "inline-flex min-w-[40px] justify-center items-center px-2 py-1 rounded-md text-xs font-medium",
        tone,
        ramp[step],
      )}
    >
      {value}
    </span>
  );
}
