import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createLeaveRequest, type LeaveTypeApi } from "@/lib/services";

const LEAVE_TYPES: { value: LeaveTypeApi; label: string }[] = [
  { value: "paid", label: "Paid" },
  { value: "sick", label: "Sick" },
  { value: "work_from_home", label: "Work from home" },
  { value: "unpaid", label: "Unpaid" },
];

type Props = {
  onCreated?: () => void;
};

export function LeaveRequestDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [leaveType, setLeaveType] = useState<LeaveTypeApi>("paid");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setStartDate("");
    setEndDate("");
    setLeaveType("paid");
    setReason("");
  };

  const handleSubmit = async () => {
    if (!startDate || !endDate) {
      toast.error("Choose start and end dates.");
      return;
    }
    setSubmitting(true);
    const result = await createLeaveRequest({
      startDate,
      endDate,
      leaveType,
      reason: reason || undefined,
    });
    setSubmitting(false);
    if (!result.ok) {
      toast.error(result.error);
      return;
    }
    if (result.overlapWarning) toast.message("Overlap notice", { description: result.overlapWarning });
    toast.success("Leave request submitted.");
    reset();
    setOpen(false);
    onCreated?.();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="shrink-0">
          Request leave
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Request time off</DialogTitle>
          <DialogDescription>Dates are sent to your manager and HR for approval.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="leave-start">Start</Label>
              <Input id="leave-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="leave-end">End</Label>
              <Input id="leave-end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Type</Label>
            <Select value={leaveType} onValueChange={(v) => setLeaveType(v as LeaveTypeApi)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LEAVE_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="leave-reason">Reason (optional)</Label>
            <Textarea id="leave-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Short note for your approver" />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleSubmit()} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
