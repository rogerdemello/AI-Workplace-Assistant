import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import {
  getWhatsappLinkStatus,
  startWhatsappLink,
  unlinkWhatsapp,
  type WhatsappLinkIssue,
  type WhatsappLinkStatus,
} from "@/lib/api/whatsapp";
import { cn } from "@/lib/utils";

export function WhatsappLinkCard() {
  const [status, setStatus] = useState<WhatsappLinkStatus | null>(null);
  const [issued, setIssued] = useState<WhatsappLinkIssue | null>(null);
  const [busy, setBusy] = useState<"idle" | "issuing" | "unlinking">("idle");
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(() => {
    void getWhatsappLinkStatus().then(setStatus);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Once a code is issued and showing, poll once a minute so the UI flips to
  // "linked" without the user having to refresh after sending the code.
  useEffect(() => {
    if (!issued && status?.status !== "pending") return;
    const interval = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(interval);
  }, [issued, status?.status, refresh]);

  // Clear the freshly-issued code from local state once the server confirms
  // it has been consumed — we trust the server, not the local timer.
  useEffect(() => {
    if (status?.status === "linked" && issued) {
      setIssued(null);
    }
  }, [status?.status, issued]);

  const issue = async () => {
    setBusy("issuing");
    const result = await startWhatsappLink();
    setBusy("idle");
    if (!result) {
      toast.error("Could not issue a WhatsApp pairing code.");
      return;
    }
    setIssued(result);
    setCopied(false);
    refresh();
  };

  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Couldn't copy. Long-press the code instead.");
    }
  };

  const remove = async () => {
    if (!window.confirm("Unlink WhatsApp? MARK will stop sending you updates there.")) return;
    setBusy("unlinking");
    const ok = await unlinkWhatsapp();
    setBusy("idle");
    if (!ok) {
      toast.error("Could not unlink WhatsApp.");
      return;
    }
    toast.success("WhatsApp unlinked.");
    setIssued(null);
    refresh();
  };

  const renderBody = () => {
    if (status === null) {
      return <p className="text-sm text-muted-foreground">Loading…</p>;
    }

    if (status.status === "linked") {
      return (
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm">
              Linked to <span className="font-mono">{status.phone_masked || "phone"}</span>.
            </div>
            {status.linked_at && (
              <div className="text-[11px] text-muted-foreground mt-1">
                Since {new Date(status.linked_at).toLocaleDateString()}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={remove}
            disabled={busy !== "idle"}
            className="text-xs px-3 py-1.5 rounded-md border border-border bg-card hover:bg-secondary transition-colors disabled:opacity-50"
          >
            {busy === "unlinking" ? "Removing…" : "Unlink"}
          </button>
        </div>
      );
    }

    const code = issued?.code || status.pending_code;
    if (code) {
      const ttl = issued?.ttl_minutes ?? 15;
      return (
        <div>
          <p className="text-sm text-muted-foreground">
            Send this code as a WhatsApp message to MARK. The code expires in {ttl} minutes.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 text-lg font-mono px-3 py-2 rounded-lg bg-secondary/60 border border-border">
              {code}
            </code>
            <button
              type="button"
              onClick={() => void copyCode(code)}
              className={cn(
                "size-9 rounded-lg border border-border grid place-items-center transition-colors",
                copied ? "text-emerald" : "text-muted-foreground hover:text-foreground",
              )}
              aria-label="Copy code"
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </button>
          </div>
          <button
            type="button"
            onClick={() => void issue()}
            disabled={busy !== "idle"}
            className="mt-3 text-xs text-accent hover:underline disabled:opacity-50"
          >
            {busy === "issuing" ? "Issuing…" : "Issue a new code"}
          </button>
        </div>
      );
    }

    return (
      <div>
        <p className="text-sm text-muted-foreground">
          Link your WhatsApp to receive HR replies, leave decisions, and reminders on your phone.
        </p>
        <button
          type="button"
          onClick={() => void issue()}
          disabled={busy !== "idle"}
          className="mt-3 text-sm px-4 py-2 rounded-lg bg-ink text-primary-foreground font-medium disabled:opacity-50"
        >
          {busy === "issuing" ? "Issuing code…" : "Link WhatsApp"}
        </button>
      </div>
    );
  };

  return (
    <div className="mt-10 rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <MessageCircle className="size-4 text-muted-foreground" />
        <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">WhatsApp</div>
      </div>
      {renderBody()}
    </div>
  );
}
