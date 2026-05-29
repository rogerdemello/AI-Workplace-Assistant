import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Briefcase, FileText, KeyRound, LogOut, PencilLine } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  listOffboardingTasks,
  patchOffboardingTask,
  type OffboardingTask,
} from "@/lib/api/offboarding";

const KIND_ICON: Record<string, typeof Briefcase> = {
  clearance: KeyRound,
  handover: Briefcase,
  kt: FileText,
  exit: LogOut,
  custom: PencilLine,
};

const KIND_LABEL: Record<string, string> = {
  clearance: "Clearance",
  handover: "Handover",
  kt: "Knowledge transfer",
  exit: "Exit",
  custom: "Custom",
};

function formatDue(iso: string | null): string {
  if (!iso) return "";
  // YYYY-MM-DD → short, locale-friendly
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function OffboardingClearanceCard({ userId }: { userId: string }) {
  const [tasks, setTasks] = useState<OffboardingTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listOffboardingTasks(userId).then((rows) => {
      if (cancelled) return;
      setTasks(rows);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
        Loading offboarding tasks…
      </div>
    );
  }

  // No tasks → user isn't being offboarded; render nothing so the page stays clean.
  if (tasks.length === 0) return null;

  const done = tasks.filter((t) => t.completed).length;
  const total = tasks.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  async function toggle(task: OffboardingTask) {
    setBusyId(task.id);
    const updated = await patchOffboardingTask(task.id, { completed: !task.completed });
    setBusyId(null);
    if (!updated) return;
    setTasks((current) => current.map((t) => (t.id === task.id ? updated : t)));
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            Offboarding clearance
          </div>
          <div className="text-sm font-medium mt-0.5">
            {done} of {total} done
          </div>
        </div>
        <div className="text-xs text-muted-foreground">{pct}%</div>
      </div>

      <div className="h-1 w-full rounded-full bg-secondary mb-4 overflow-hidden">
        <div
          className="h-full bg-emerald-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ul className="space-y-2">
        {tasks.map((t) => {
          const Icon = KIND_ICON[t.kind] ?? PencilLine;
          const busy = busyId === t.id;
          return (
            <li
              key={t.id}
              className={cn(
                "flex items-start gap-3 p-2.5 rounded-lg border border-border/70 bg-secondary/30",
                t.completed && "opacity-70",
              )}
            >
              <button
                type="button"
                onClick={() => toggle(t)}
                disabled={busy}
                className="shrink-0 mt-0.5"
                aria-label={t.completed ? "Mark incomplete" : "Mark complete"}
              >
                {t.completed ? (
                  <CheckCircle2 className="size-5 text-emerald-500" />
                ) : (
                  <Circle className="size-5 text-muted-foreground" />
                )}
              </button>
              <Icon className="size-3.5 mt-1 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div
                  className={cn(
                    "text-sm leading-tight",
                    t.completed && "line-through text-muted-foreground",
                  )}
                >
                  {t.title}
                </div>
                <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-2 flex-wrap">
                  <span>{KIND_LABEL[t.kind] ?? t.kind}</span>
                  {t.due_date && <span>· due {formatDue(t.due_date)}</span>}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
