import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { getEmployees } from "@/lib/api/people";
import type { Employee } from "@/lib/domain-types";

type SortKey = "risk" | "sentiment" | "name";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "risk", label: "Risk" },
  { key: "sentiment", label: "Sentiment" },
  { key: "name", label: "Name" },
];

export function AtRiskEmployeesCard({ limit = 10 }: { limit?: number }) {
  const [rows, setRows] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<SortKey>("risk");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getEmployees()
      .then((data) => {
        if (!cancelled) {
          setRows(data ?? []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const top = useMemo(() => {
    const sorted = [...rows];
    if (sort === "risk") {
      sorted.sort((a, b) => (b.riskScore ?? 0) - (a.riskScore ?? 0));
    } else if (sort === "sentiment") {
      sorted.sort((a, b) => (a.sentimentScore ?? 100) - (b.sentimentScore ?? 100));
    } else {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted.slice(0, limit);
  }, [rows, sort, limit]);

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">At-risk employees</div>
          <div className="text-sm font-medium mt-0.5">Top {limit} by current risk score</div>
        </div>
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSort(s.key)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-md transition-colors",
                sort === s.key
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-10 text-center text-sm text-muted-foreground">Loading…</div>
      ) : top.length === 0 ? (
        <div className="py-10 text-center text-sm text-muted-foreground">No employee data yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="text-left font-medium pb-2">Employee</th>
                <th className="text-left font-medium pb-2 px-2">Department</th>
                <th className="text-right font-medium pb-2 px-2">Sentiment</th>
                <th className="text-right font-medium pb-2 px-2">Risk</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {top.map((e) => (
                <tr key={e.id} className="border-t border-border/60">
                  <td className="py-2 pr-2 font-medium">{e.name}</td>
                  <td className="py-2 px-2 text-muted-foreground">{e.department || "—"}</td>
                  <td className="py-2 px-2 text-right">
                    <SentimentChip sentiment={e.sentiment} score={e.sentimentScore} />
                  </td>
                  <td className="py-2 px-2 text-right">
                    <RiskChip score={e.riskScore} label={e.riskLabel} />
                  </td>
                  <td className="py-2 pl-2 text-right">
                    <Link
                      to={`/employees/${e.id}`}
                      className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                    >
                      Profile <ArrowUpRight className="size-3" />
                    </Link>
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

function SentimentChip({
  sentiment,
  score,
}: {
  sentiment: Employee["sentiment"];
  score?: number;
}) {
  const tone =
    sentiment === "at_risk"
      ? "bg-danger-soft text-danger"
      : sentiment === "watch"
        ? "bg-warning-soft text-warning"
        : sentiment === "positive"
          ? "bg-emerald-soft text-emerald"
          : "bg-secondary text-muted-foreground";
  return (
    <span className={cn("inline-flex px-2 py-0.5 rounded-md text-[11px] font-medium", tone)}>
      {score == null ? "—" : Math.round(score)}
    </span>
  );
}

function RiskChip({ score, label }: { score?: number; label?: Employee["riskLabel"] }) {
  if (score == null) {
    return <span className="text-[11px] text-muted-foreground">—</span>;
  }
  const tone =
    score >= 70
      ? "bg-danger-soft text-danger"
      : score >= 40
        ? "bg-warning-soft text-warning"
        : "bg-emerald-soft text-emerald";
  return (
    <span className={cn("inline-flex px-2 py-0.5 rounded-md text-[11px] font-medium", tone)}>
      {label ? `${label} · ${score}` : score}
    </span>
  );
}
