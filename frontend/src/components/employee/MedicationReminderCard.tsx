import { useCallback, useEffect, useState } from "react";
import { Pill, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  cancelReminder,
  createMedicationReminder,
  getMyReminders,
  type ReminderRow,
} from "@/lib/api/portal";

const formatTime = (iso: string | null): string => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export function MedicationReminderCard() {
  const [meds, setMeds] = useState<ReminderRow[]>([]);
  const [name, setName] = useState("");
  const [time, setTime] = useState("09:00");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    void getMyReminders().then((rows) =>
      setMeds(rows.filter((r) => r.reminder_type === "medication" && r.status !== "cancelled")),
    );
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = async () => {
    if (!name.trim()) {
      toast.error("Enter a medication name.");
      return;
    }
    setBusy(true);
    const row = await createMedicationReminder({ medication: name, time });
    setBusy(false);
    if (!row) {
      toast.error("Could not set the reminder.");
      return;
    }
    toast.success(`Daily reminder set for ${name.trim()}.`);
    setName("");
    refresh();
  };

  const remove = async (id: string) => {
    const ok = await cancelReminder(id);
    if (!ok) {
      toast.error("Could not remove the reminder.");
      return;
    }
    refresh();
  };

  return (
    <div className="mt-10 rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Pill className="size-4 text-muted-foreground" />
        <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Medication reminders</div>
      </div>

      <p className="text-sm text-muted-foreground mb-3">
        I'll nudge you in chat each day at the time you set. We only store the name and time — nothing about why.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[160px]">
          <label className="text-[11px] text-muted-foreground">Medication</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Vitamin D"
            className="w-full bg-secondary/40 rounded-lg px-3 py-2 text-sm outline-none focus:bg-secondary/60 transition-colors"
          />
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground">Time</label>
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="bg-secondary/40 rounded-lg px-3 py-2 text-sm outline-none focus:bg-secondary/60 transition-colors"
          />
        </div>
        <button
          type="button"
          onClick={() => void add()}
          disabled={busy || !name.trim()}
          className="text-sm px-4 py-2 rounded-lg bg-ink text-primary-foreground font-medium disabled:opacity-50"
        >
          {busy ? "Setting…" : "Add"}
        </button>
      </div>

      {meds.length > 0 && (
        <ul className="mt-4 space-y-2">
          {meds.map((m) => (
            <li
              key={m.id}
              className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 px-3 py-2"
            >
              <span className="text-sm">
                {m.title.replace(/^Medication:\s*/, "")}
                <span className="text-muted-foreground"> · daily {formatTime(m.next_trigger_at)}</span>
              </span>
              <button
                type="button"
                onClick={() => void remove(m.id)}
                className="text-muted-foreground hover:text-danger transition-colors"
                aria-label="Remove reminder"
              >
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
