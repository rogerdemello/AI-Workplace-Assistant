import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cancelLeaveRequest, listLeaveRequests, type LeaveRow } from "@/lib/services";

type Props = {
  onChanged?: () => void;
};

function formatLeaveRange(row: LeaveRow): string {
  if (!row.startDate || !row.endDate) return "—";
  return `${row.startDate} → ${row.endDate}`;
}

export function MyLeaveRequests({ onChanged }: Props) {
  const [rows, setRows] = useState<LeaveRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    void listLeaveRequests().then((list) => setRows(list.slice(0, 8)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCancel = async (id: string) => {
    setBusyId(id);
    const done = await cancelLeaveRequest(id);
    setBusyId(null);
    if (!done) {
      toast.error("Could not cancel this request.");
      return;
    }
    toast.success("Leave request cancelled.");
    load();
    onChanged?.();
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Time off</div>
          <div className="font-medium mt-0.5">Your recent requests</div>
        </div>
        <Button type="button" variant="ghost" size="sm" className="text-xs" onClick={() => load()}>
          Refresh
        </Button>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No leave requests yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 py-2 border-b border-border last:border-0 text-sm">
              <div>
                <div className="text-foreground">{formatLeaveRange(r)}</div>
                <div className="text-xs text-muted-foreground capitalize mt-0.5">
                  {r.leaveType.replace(/_/g, " ")} · <span className="font-medium text-foreground">{r.status}</span>
                </div>
              </div>
              {r.status === "pending" && (
                <Button type="button" variant="outline" size="sm" disabled={busyId === r.id} onClick={() => void handleCancel(r.id)}>
                  {busyId === r.id ? "Cancelling…" : "Cancel"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
