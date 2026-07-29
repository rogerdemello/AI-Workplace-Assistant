import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Sparkles, RefreshCw, Send, Copy, Check, MessageSquareText } from "lucide-react";
import { draftEmail, sendEmail } from "@/lib/services";
import { toast } from "sonner";

const samples = [
  "Notify the team that the office will be closed on Friday for maintenance. Be warm and brief.",
  "Reply to a candidate declining their offer with grace, leave the door open.",
  "Tell engineering about new on-call policy starting next month.",
];

export default function EmailAssistant() {
  const [searchParams] = useSearchParams();
  const conversationId = useMemo(() => searchParams.get("conversation_id") || undefined, [searchParams]);
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [ctx, setCtx] = useState("");
  const [tone, setTone] = useState("Warm");
  const [draft, setDraft] = useState("");
  const [subject, setSubject] = useState("");
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<string | null>(null);
  const [groundedInConversation, setGroundedInConversation] = useState(false);

  const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
  const parseCcEmails = (input: string): string[] =>
    input
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const generate = async () => {
    if (!ctx.trim()) return;
    setGenerating(true);
    setDraft("");
    setSubject("");
    setError(null);
    setSendStatus(null);
    const result = await draftEmail({ context: ctx, toneLabel: tone, conversationId });
    setGenerating(false);
    if (!result) {
      setError("Could not reach the email draft API. Check login and backend availability.");
      toast.error("Could not draft email.");
      return;
    }
    setSubject(result.subject);
    setDraft(result.body);
    setGroundedInConversation(result.groundedInConversation);
    toast.success(result.groundedInConversation ? "Draft ready (grounded in your recent chat)." : "Draft ready.");
  };

  const copy = async () => {
    const text = subject ? `Subject: ${subject}\n\n${draft}` : draft;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      toast.success("Copied draft to clipboard.");
    } catch {
      toast.error("Could not copy to clipboard.");
    }
  };

  const openInDefaultMailApp = () => {
    if (!draft.trim()) return;
    if (!isValidEmail(to)) {
      toast.error("Enter a valid recipient email.");
      return;
    }
    const subj = encodeURIComponent(subject.trim() || "HR message");
    const body = encodeURIComponent(draft);
    const recipient = encodeURIComponent(to.trim());
    window.location.assign(`mailto:${recipient}?subject=${subj}&body=${body}`);
  };

  const handleSend = async () => {
    if (!to.trim() || !draft.trim()) return;
    if (!isValidEmail(to)) {
      const message = "Recipient email is invalid.";
      setSendStatus(message);
      toast.error(message);
      return;
    }
    const ccEmails = parseCcEmails(cc);
    const invalidCc = ccEmails.find((item) => !isValidEmail(item));
    if (invalidCc) {
      const message = `Invalid CC email: ${invalidCc}`;
      setSendStatus(message);
      toast.error(message);
      return;
    }
    setSending(true);
    setSendStatus(null);
    const result = await sendEmail({
      to: to.trim(),
      subject: subject.trim() || "HR message",
      body: draft,
      cc: ccEmails,
    });
    setSending(false);
    if (!result.ok) {
      setSendStatus(result.error);
      toast.error(result.error);
      return;
    }
    setSendStatus(result.detail);
    toast.success(result.detail);
  };

  return (
    <AppLayout title="Email Assistant" subtitle="Compose hard messages — with care.">
      <div className="px-6 lg:px-10 py-8 max-w-6xl grid lg:grid-cols-2 gap-6">
        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-4">What needs to be said?</div>
          <input
            type="email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="Recipient email"
            className="w-full bg-secondary/40 rounded-xl px-4 py-3 text-sm outline-none focus:bg-secondary/60 transition-colors mb-3"
          />
          <input
            type="text"
            value={cc}
            onChange={(e) => setCc(e.target.value)}
            placeholder="CC emails (comma separated)"
            className="w-full bg-secondary/40 rounded-xl px-4 py-3 text-sm outline-none focus:bg-secondary/60 transition-colors mb-3"
          />
          <textarea
            value={ctx}
            onChange={(e) => setCtx(e.target.value)}
            rows={8}
            placeholder="Describe the message — context, audience, anything tricky."
            className="w-full bg-secondary/40 rounded-xl p-4 text-sm outline-none focus:bg-secondary/60 transition-colors resize-none"
          />

          <div className="mt-4">
            <div className="text-xs text-muted-foreground mb-2">Tone</div>
            <div className="flex flex-wrap gap-1.5">
              {["Warm", "Direct", "Empathetic", "Formal", "Brief"].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTone(t)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    tone === t ? "bg-ink text-primary-foreground border-foreground" : "bg-card border-border hover:border-foreground/30"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="text-xs text-muted-foreground mb-2">Or try a starting point</div>
            <div className="space-y-1.5">
              {samples.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setCtx(s)}
                  className="block w-full text-left text-xs text-muted-foreground hover:text-foreground p-2 rounded-md hover:bg-secondary/60 transition-colors"
                >
                  → {s}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="mt-4 text-xs text-danger">{error}</p>}
          {sendStatus && <p className="mt-2 text-xs text-muted-foreground">{sendStatus}</p>}

          <button
            type="button"
            onClick={() => void generate()}
            disabled={generating || !ctx.trim()}
            className="mt-6 w-full h-11 rounded-lg bg-ink text-primary-foreground text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {generating ? <RefreshCw className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {generating ? "Drafting…" : "Draft email"}
          </button>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 flex flex-col">
          <div className="flex items-center justify-between mb-4 gap-2">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Draft</div>
            {conversationId && (
              <div
                className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full border border-border bg-secondary/40 text-muted-foreground"
                title={
                  groundedInConversation
                    ? "This draft was grounded in your recent chat."
                    : "We'll use context from your recent chat when you draft."
                }
              >
                <MessageSquareText className="size-3" />
                {groundedInConversation ? "Using chat context" : "Chat context ready"}
              </div>
            )}
          </div>
          <div className="flex-1 min-h-[200px] rounded-xl bg-secondary/30 p-4 text-sm whitespace-pre-wrap">
            {subject && <div className="font-medium mb-2">Subject: {subject}</div>}
            {draft || <span className="text-muted-foreground">Generated email will appear here.</span>}
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => void copy()}
              disabled={!draft}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-sm disabled:opacity-50"
            >
              {copied ? <Check className="size-4 text-emerald" /> : <Copy className="size-4" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={() => openInDefaultMailApp()}
              disabled={!draft.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-secondary/80 transition-colors disabled:opacity-50"
              title="Opens your desktop or web mail client with this draft"
            >
              <Send className="size-4" /> Open in mail app
            </button>
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!to.trim() || !draft.trim() || sending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ink text-primary-foreground text-sm font-medium disabled:opacity-50"
            >
              {sending ? <RefreshCw className="size-4 animate-spin" /> : <Send className="size-4" />}
              {sending ? "Sending…" : "Send via SMTP"}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
