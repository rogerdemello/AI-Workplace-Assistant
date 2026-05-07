import { cn } from "@/lib/utils";
import type { Sentiment } from "@/lib/domain-types";

const sentimentMap: Record<Sentiment, { label: string; cls: string; dot: string }> = {
  positive: { label: "Thriving", cls: "bg-emerald-soft text-emerald", dot: "bg-emerald" },
  neutral:  { label: "Steady",   cls: "bg-secondary text-secondary-foreground", dot: "bg-muted-foreground" },
  watch:    { label: "Watch",    cls: "bg-warning-soft text-warning", dot: "bg-warning" },
  at_risk:  { label: "At risk",  cls: "bg-danger-soft text-danger", dot: "bg-danger" },
};

export function SentimentBadge({ sentiment, className }: { sentiment: Sentiment; className?: string }) {
  const s = sentimentMap[sentiment];
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium", s.cls, className)}>
      <span className={cn("size-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}

export function PriorityPill({ priority }: { priority: "low" | "medium" | "high" | "urgent" }) {
  const map = {
    low: "bg-secondary text-muted-foreground",
    medium: "bg-secondary text-foreground",
    high: "bg-warning-soft text-warning",
    urgent: "bg-danger-soft text-danger",
  };
  return <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium uppercase tracking-wide", map[priority])}>{priority}</span>;
}

export function StatusPill({ status }: { status: "open" | "in_progress" | "resolved" | "escalated" }) {
  const map = {
    open: { label: "Open", cls: "bg-accent-soft text-accent" },
    in_progress: { label: "In progress", cls: "bg-secondary text-foreground" },
    resolved: { label: "Resolved", cls: "bg-emerald-soft text-emerald" },
    escalated: { label: "Escalated", cls: "bg-danger-soft text-danger" },
  };
  const s = map[status];
  return <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", s.cls)}>{s.label}</span>;
}

export function Avatar({ initials, size = "md", tone = "ink" }: { initials: string; size?: "sm" | "md" | "lg"; tone?: "ink" | "teal" }) {
  const sizeCls = { sm: "size-7 text-[10px]", md: "size-9 text-xs", lg: "size-12 text-sm" }[size];
  const toneCls = tone === "teal" ? "bg-teal-grad text-primary-foreground" : "bg-ink text-primary-foreground";
  return <div className={cn("rounded-full grid place-items-center font-medium shrink-0", sizeCls, toneCls)}>{initials}</div>;
}
