import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { mergeEmployeeDirectoryRows } from "@/lib/api/people";
import { apiBaseUrl, readStoredSession } from "@/lib/api/client";
import { ensureSessionToken } from "@/lib/chat-api";
import type { Employee } from "@/lib/domain-types";
import { Avatar, SentimentBadge } from "@/components/ui-bits";
import { Search, ArrowUpRight, Zap, Moon } from "lucide-react";
import { cn } from "@/lib/utils";

type DirectoryError = "none" | "auth" | "forbidden" | "network";

export default function Employees() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [list, setList] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [directoryError, setDirectoryError] = useState<DirectoryError>("none");
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [dept, setDept] = useState(searchParams.get("dept") || "all");
  const [riskFilter, setRiskFilter] = useState(searchParams.get("risk") || "all");
  const [managerIdFilter, setManagerIdFilter] = useState(searchParams.get("managerId") || "");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setDirectoryError("none");
      try {
        const token = await ensureSessionToken(readStoredSession());
        if (!token) {
          if (!cancelled) {
            setDirectoryError("auth");
            setList([]);
          }
          return;
        }
        const headers = { Authorization: `Bearer ${token}` };
        const base = apiBaseUrl();
        const [usersRes, analyticsRes] = await Promise.all([
          fetch(`${base}/api/v1/users`, { headers }),
          fetch(`${base}/api/v1/analytics/employees`, { headers }),
        ]);
        if (cancelled) return;
        if (usersRes.status === 401 || analyticsRes.status === 401) {
          setDirectoryError("auth");
          setList([]);
          return;
        }
        if (usersRes.status === 403 || analyticsRes.status === 403) {
          setDirectoryError("forbidden");
          setList([]);
          return;
        }
        let usersPayload: Array<Record<string, unknown>> | null = null;
        let analyticsPayload: Array<Record<string, unknown>> | null = null;
        try {
          if (usersRes.ok) {
            usersPayload = (await usersRes.json()) as Array<Record<string, unknown>>;
          }
          if (analyticsRes.ok) {
            analyticsPayload = (await analyticsRes.json()) as Array<Record<string, unknown>>;
          }
        } catch {
          setDirectoryError("network");
          setList([]);
          return;
        }
        const merged = mergeEmployeeDirectoryRows(usersPayload, analyticsPayload);
        setList(merged);
      } catch {
        if (!cancelled) {
          setDirectoryError("network");
          setList([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const departments = useMemo(() => ["all", ...Array.from(new Set(list.map(e => e.department)))], [list]);
  const managerNameById = useMemo(() => {
    const map = new Map<string, string>();
    list.forEach((employee) => {
      if (employee.id) map.set(employee.id, employee.name);
    });
    return map;
  }, [list]);
  const managerScopeLabel = managerIdFilter
    ? (managerNameById.get(managerIdFilter) ?? managerIdFilter)
    : "";
  const filtered = list.filter((e) => {
    const matchesDept = dept === "all" || e.department === dept;
    const matchesQuery = !q || (e.name + e.role + e.email).toLowerCase().includes(q.toLowerCase());
    const matchesManager = !managerIdFilter || e.managerId === managerIdFilter;
    const matchesRisk =
      riskFilter === "all" ||
      (riskFilter === "at_risk" && e.riskScore >= 60) ||
      (riskFilter === "watch" && e.riskScore >= 35 && e.riskScore < 60);
    return matchesDept && matchesQuery && matchesManager && matchesRisk;
  });

  useEffect(() => {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    if (dept !== "all") next.set("dept", dept);
    if (riskFilter !== "all") next.set("risk", riskFilter);
    if (managerIdFilter) next.set("managerId", managerIdFilter);
    setSearchParams(next, { replace: true });
  }, [q, dept, riskFilter, managerIdFilter, setSearchParams]);

  const exportCsv = () => {
    const header = ["Name", "Role", "Department", "Email", "Sentiment", "SentimentScore", "Trend", "Delta", "RiskScore", "RiskLabel"];
    const rows = filtered.map((employee) => [
      employee.name,
      employee.role,
      employee.department,
      employee.email,
      employee.sentiment,
      String(employee.sentimentScore ?? 50),
      String(employee.sentimentTrend ?? "stable"),
      String(employee.sentimentDelta ?? 0),
      String(employee.riskScore),
      String(employee.riskLabel ?? "Low"),
    ]);
    const csv = [header, ...rows]
      .map((row) =>
        row
          .map((cell) => `"${String(cell).replaceAll('"', '""')}"`)
          .join(","),
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "employees-filtered.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppLayout title="Employees" subtitle="Your team — with sentiment and risk surfaced">
      <div className="px-6 lg:px-10 py-8 max-w-7xl">
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex items-center gap-2 px-3 h-10 rounded-lg bg-card border border-border w-72">
            <Search className="size-4 text-muted-foreground" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search employees…" className="flex-1 bg-transparent text-sm outline-none" />
          </div>
          <div className="flex gap-1 p-1 rounded-lg bg-secondary overflow-x-auto">
            {departments.map(d => (
              <button key={d} onClick={() => setDept(d)} className={cn(
                "text-xs px-2.5 py-1 rounded-md whitespace-nowrap transition-colors",
                dept === d ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
              )}>{d === "all" ? "All teams" : d}</button>
            ))}
          </div>
          <div className="flex gap-1 p-1 rounded-lg bg-secondary">
            {[
              ["all", "All risk"],
              ["watch", "Watch"],
              ["at_risk", "At risk"],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setRiskFilter(value)}
                className={cn(
                  "text-xs px-2.5 py-1 rounded-md whitespace-nowrap transition-colors",
                  riskFilter === value ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {managerIdFilter && (
            <button
              onClick={() => setManagerIdFilter("")}
              className="text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary transition-colors"
              title="Clear manager filter"
            >
              Manager: {managerScopeLabel} ×
            </button>
          )}
          <button
            onClick={exportCsv}
            className="ml-auto text-xs px-3 h-8 rounded-md border border-border bg-card hover:bg-secondary transition-colors"
          >
            Export CSV
          </button>
          <div className="text-xs text-muted-foreground">{filtered.length} people</div>
        </div>

        {loading && (
          <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
            Loading employee directory…
          </div>
        )}

        {!loading && directoryError === "auth" && (
          <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
            Your session expired or the token is invalid — please log out and sign in again (HR account:{" "}
            <span className="font-mono text-xs">hr1@infeedo.ai</span>).
          </div>
        )}

        {!loading && directoryError === "forbidden" && (
          <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
            This page is restricted to HR. If you reached it by URL, use an HR login.
          </div>
        )}

        {!loading && directoryError === "network" && (
          <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
            Could not load the directory (network or server error). Check that the API is running and{" "}
            <code className="text-xs">VITE_API_URL</code> points to it, then refresh.
          </div>
        )}

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {!loading &&
            directoryError === "none" &&
            filtered.map((e) => (
            <Link key={e.id} to={`/employees/${e.id}`} className="group rounded-2xl border border-border bg-card p-5 hover:shadow-elevated transition-shadow">
              <div className="flex items-start gap-3">
                <Avatar initials={e.initials} size="lg" tone={e.sentiment === "positive" ? "teal" : "ink"} />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium truncate">{e.name}</span>
                    {e.spikeAlert && (
                      <span className="shrink-0 text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-danger-soft text-danger font-medium inline-flex items-center gap-0.5" title="Sentiment spike">
                        <Zap className="size-3" />
                      </span>
                    )}
                    {e.silentRisk && (
                      <span className="shrink-0 text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-warning-soft text-warning font-medium inline-flex items-center gap-0.5" title="Quiet risk">
                        <Moon className="size-3" />
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">{e.role} · {e.department}</div>
                </div>
                <ArrowUpRight className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="mt-4 flex items-center justify-between">
                <SentimentBadge sentiment={e.sentiment} />
                <div className="text-xs text-muted-foreground">
                  Risk{" "}
                  <span className={cn("font-medium", e.riskScore > 60 ? "text-danger" : e.riskScore > 35 ? "text-warning" : "text-emerald")}>
                    {e.riskScore}
                  </span>
                  {e.riskLabel ? ` · ${e.riskLabel}` : ""}
                </div>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                Sentiment {Math.round(e.sentimentScore ?? 50)}%
                {" · "}
                {e.sentimentTrend === "down" ? "↓ declining" : e.sentimentTrend === "up" ? "↑ improving" : "→ stable"}
                {" · "}
                Δ {e.sentimentDelta ?? 0}
              </div>
              <div className="mt-3 h-1 rounded-full bg-secondary overflow-hidden">
                <div className={cn("h-full rounded-full transition-all",
                  e.riskScore > 60 ? "bg-danger" : e.riskScore > 35 ? "bg-warning" : "bg-emerald"
                )} style={{ width: `${e.riskScore}%` }} />
              </div>
            </Link>
            ))}
          {!loading && directoryError === "none" && filtered.length === 0 && (
            <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
              No employees match these filters, or the database has no employee rows yet. From <code className="text-xs">backend/</code> run:{" "}
              <code className="text-xs">python -m scripts.seed_dummy_users</code>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
