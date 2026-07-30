import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { updateMyProfile } from "@/lib/api/people";
import { toast } from "sonner";

interface Props {
  open: boolean;
  initialName: string;
  initialDesignation: string;
  onClose: () => void;
  onSaved: () => void;
}

export function EditProfileDialog({ open, initialName, initialDesignation, onClose, onSaved }: Props) {
  const [name, setName] = useState(initialName);
  const [designation, setDesignation] = useState(initialDesignation);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName(initialName);
      setDesignation(initialDesignation);
    }
  }, [open, initialName, initialDesignation]);

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Name can't be empty.");
      return;
    }
    setSaving(true);
    const ok = await updateMyProfile({ name: name.trim(), designation: designation.trim() });
    setSaving(false);
    if (!ok) {
      toast.error("Could not save changes. Please try again.");
      return;
    }
    toast.success("Profile updated.");
    onSaved();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit profile</DialogTitle>
          <DialogDescription>Update your displayed name and designation.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="profile-name">Name</Label>
            <Input id="profile-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="profile-designation">Designation</Label>
            <Input
              id="profile-designation"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              maxLength={120}
              placeholder="e.g. Software Engineer"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
