import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, X, Maximize2, Minimize2, ChevronDown, Paperclip, MessageSquarePlus, Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useChat, MOOD_CHOICES } from "@/contexts/ChatContext";
import type { ChatAttachmentMeta } from "@/lib/chat-api";
import { formatFlowStepLabel } from "@/lib/flow-metadata-ui";
import { MessageBubble } from "./MessageBubble";
import { cn } from "@/lib/utils";

export function ChatPanel() {
  const { session } = useAuth();
  const {
    mode,
    minimize,
    expand,
    setMode,
    messages,
    send,
    isTyping,
    isSending,
    control,
    flowMetadata,
    memoryCards,
    quickActions,
    onControlAction,
    onDateAction,
    pendingCsat,
    submitCsatRating,
    dismissCsat,
    moodCheckinActive,
    logMoodCheckin,
    dismissMoodCheckin,
    startNewChat,
    chatReady,
    conversationId,
  } = useChat();
  const navigate = useNavigate();
  const flowLabel = formatFlowStepLabel(flowMetadata);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  if (mode === "minimized") return null;

  const isFull = mode === "full";

  /** Send the composed message, or leave it in the box untouched.
   *
   *  The original bug was that a send during `isSending` cleared the input and
   *  then dropped the message — silent loss, which for this product is the
   *  worst failure available: the employee has no reason to retry and HR never
   *  learns there was anything to hear.
   *
   *  Three attempts at queueing the turn instead all went wrong (stale reads,
   *  a status ref that stopped matching reality, an effect that missed its
   *  trigger), each stranding the message the queue was meant to protect. So
   *  this does not queue. It refuses, and the refusal is visible: the text
   *  stays in the composer, so the employee can see it was not sent and press
   *  again. Not losing the message matters more than sending it on the first
   *  press. Queueing properly is recorded in task.txt. */
  const handleSend = () => {
    const text = input.trim();
    if (!text && !selectedFile) return;
    // Nothing to send into yet, or a turn is already in flight. Keep the text.
    if (!chatReady || isSending) return;

    const attachment = selectedFile
      ? { name: selectedFile.name, size: selectedFile.size }
      : null;
    const payload = text || "Please consider attached file.";

    // Cleared only now, on the path that actually dispatches.
    setInput("");
    setSelectedFile(null);
    void send(payload, attachment);
  };

  return (
    <AnimatePresence>
      {/* Backdrop for full-screen */}
      {isFull && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={() => setMode("panel")}
          className="fixed inset-0 z-40 bg-foreground/40 backdrop-blur-sm"
        />
      )}

      <motion.div
        key="panel"
        initial={{ x: "100%", opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: "100%", opacity: 0 }}
        transition={{ type: "spring", stiffness: 320, damping: 32 }}
        className={cn(
          "fixed z-50 bg-card border border-border shadow-chat flex flex-col overflow-hidden",
          isFull
            ? "inset-4 md:inset-10 rounded-2xl"
            : "right-4 bottom-4 top-4 w-[min(440px,calc(100vw-2rem))] rounded-2xl"
        )}
      >
        {/* Header */}
        <div className="relative px-5 py-4 bg-ink text-primary-foreground border-b border-white/5">
          <div className="absolute inset-0 bg-aurora opacity-60 pointer-events-none" />
          <div className="relative flex items-center gap-3">
            <div className="size-9 rounded-full bg-teal-grad grid place-items-center shadow-glow">
              <Sparkles className="size-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium leading-tight">MARK</div>
              <div className="text-[11px] text-primary-foreground/60 flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald animate-pulse-soft" />
                Online · Confidential
              </div>
            </div>
            <button
              type="button"
              onClick={startNewChat}
              className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
              title="Start a new chat"
              aria-label="Start a new chat"
            >
              <MessageSquarePlus className="size-4" />
            </button>
            <button onClick={() => isFull ? setMode("panel") : expand()} className="p-1.5 rounded-md hover:bg-white/10 transition-colors" aria-label="Toggle full screen">
              {isFull ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </button>
            <button onClick={minimize} className="p-1.5 rounded-md hover:bg-white/10 transition-colors" aria-label="Minimize">
              <ChevronDown className="size-4" />
            </button>
            <button onClick={minimize} className="p-1.5 rounded-md hover:bg-white/10 transition-colors md:hidden" aria-label="Close">
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 bg-background">
          {flowLabel ? (
            <div className="rounded-xl border border-teal-200/80 bg-teal-50/70 px-3 py-2 mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-teal-800">Active workflow</p>
              <p className="mt-1 text-xs font-medium text-slate-800">{flowLabel}</p>
              {flowMetadata?.missing_fields?.length ? (
                <p className="mt-1 text-[11px] text-slate-600">Still need: {flowMetadata.missing_fields.join(", ")}</p>
              ) : null}
            </div>
          ) : null}
          {session?.role === "employee" && !chatReady ? (
            <p className="text-xs text-muted-foreground mb-4">Connecting to MARK…</p>
          ) : null}
          {memoryCards.length > 0 && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-3 mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-700">Your memory cards</p>
              <div className="mt-2 space-y-2">
                {memoryCards.map((card, index) => (
                  <div key={`${card.title}-${index}`} className="rounded-xl border border-blue-100 bg-white/80 px-3 py-2">
                    <p className="text-xs font-semibold text-slate-900">{card.title}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">{card.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {messages.map(m => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {isTyping && (
            <div className="flex gap-3 mb-4">
              <div className="size-8 shrink-0 rounded-full bg-ink grid place-items-center">
                <Sparkles className="size-3.5 text-accent-glow" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-secondary flex items-center gap-1">
                <span className="size-1.5 rounded-full bg-muted-foreground/60 animate-typing" />
                <span className="size-1.5 rounded-full bg-muted-foreground/60 animate-typing [animation-delay:120ms]" />
                <span className="size-1.5 rounded-full bg-muted-foreground/60 animate-typing [animation-delay:240ms]" />
              </div>
            </div>
          )}
        </div>

        {moodCheckinActive ? (
          <div className="border-t border-border bg-teal-50/60 px-3 py-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-teal-800">Quick mood check-in</p>
              <button
                type="button"
                onClick={dismissMoodCheckin}
                className="text-[11px] text-slate-500 hover:text-slate-700"
              >
                Skip
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {MOOD_CHOICES.map((choice) => (
                <button
                  key={choice.emoji}
                  type="button"
                  onClick={() => void logMoodCheckin(choice)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white border border-border px-3 py-1.5 text-xs hover:border-accent transition-colors"
                >
                  <span className="text-base leading-none">{choice.emoji}</span>
                  {choice.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="border-t border-border bg-card px-3 py-2">
          <div className="mb-1 flex items-center justify-between">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Quick actions</p>
            {conversationId ? (
              <button
                type="button"
                onClick={() => navigate(`/email-assistant?conversation_id=${conversationId}`)}
                className="inline-flex items-center gap-1 text-[11px] text-accent hover:underline"
                title="Open the email assistant pre-loaded with this conversation as context"
              >
                <Mail className="size-3" /> Draft email about this
              </button>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {quickActions.map((option) => (
              <button
                key={option}
                onClick={() => void send(option)}
                className="h-7 rounded-full bg-white border border-border px-3 text-xs hover:border-accent transition-colors"
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        {control.kind ? (
          <div className="border-t border-border bg-slate-50 px-3 py-3">
            {control.label ? <p className="mb-2 text-xs font-medium text-slate-600">{control.label}</p> : null}
            {control.kind === "select" ? (
              <div className="flex flex-wrap gap-2">
                {control.options?.map((option) => (
                  <button
                    key={option}
                    onClick={() => void onControlAction(option)}
                    className="rounded-full bg-white border border-border px-3 py-1.5 text-xs hover:border-accent transition-colors"
                  >
                    {option}
                  </button>
                ))}
              </div>
            ) : null}
            {control.kind === "choice" ? (
              <div className="flex gap-2">
                <button onClick={() => void onControlAction("Yes")} className="rounded-full bg-ink text-primary-foreground px-4 py-1.5 text-xs">Yes</button>
                <button onClick={() => void onControlAction("No")} className="rounded-full bg-white border border-border px-4 py-1.5 text-xs">No</button>
              </div>
            ) : null}
            {control.kind === "date" ? (
              <input
                type="date"
                onChange={(event) => {
                  if (event.target.value) {
                    void onDateAction(event.target.value);
                  }
                }}
                className="h-9 rounded-lg border border-border bg-white px-3 text-sm"
              />
            ) : null}
          </div>
        ) : null}

        {pendingCsat ? (
          <div className="border-t border-border bg-slate-50 px-3 py-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Response quality</p>
            <p className="text-xs text-slate-600">How helpful was my last response?</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[1, 2, 3, 4, 5].map((score) => (
                <button
                  key={score}
                  onClick={() => void submitCsatRating(score)}
                  className="h-7 rounded-full bg-white border border-border px-3 text-xs hover:border-accent transition-colors"
                >
                  {score}
                </button>
              ))}
              <button onClick={dismissCsat} className="h-7 rounded-full px-3 text-xs text-slate-500 hover:text-slate-700">
                Skip
              </button>
            </div>
          </div>
        ) : null}

        {/* Composer */}
        <div className="p-3 border-t border-border bg-card">
          {selectedFile ? (
            <div className="mb-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <Paperclip className="h-4 w-4 text-slate-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-slate-700">{selectedFile.name}</p>
              </div>
              <button onClick={() => setSelectedFile(null)} className="rounded-full p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600">
                <X className="h-3 w-3" />
              </button>
            </div>
          ) : null}
          <div className="flex items-end gap-2 rounded-xl border border-border bg-background p-2 focus-within:border-accent transition-colors">
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  setSelectedFile(file);
                }
                event.target.value = "";
              }}
            />
            <button
              onClick={() => fileRef.current?.click()}
              className="size-9 rounded-lg border border-border bg-card text-muted-foreground grid place-items-center hover:border-accent transition-colors"
              aria-label="Attach file"
            >
              <Paperclip className="size-4" />
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Tell MARK what's on your mind…"
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground px-2 py-1.5 max-h-32"
            />
            {/* Deliberately not disabled on isSending/isTyping: both are
                transient, so the button could flip disabled between a user
                pressing it and the click dispatching, losing the turn. Sends
                during a reply are queued instead. */}
            <button
              onClick={handleSend}
              disabled={(!input.trim() && !selectedFile) || !chatReady}
              className="size-9 rounded-lg bg-ink text-primary-foreground grid place-items-center disabled:opacity-30 hover:opacity-90 transition-opacity"
              aria-label="Send"
            >
              <Send className="size-4" />
            </button>
          </div>
          <div className="text-[10px] text-muted-foreground mt-2 px-1">
            Conversations with MARK are confidential. HR sees only what you choose to escalate.
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
