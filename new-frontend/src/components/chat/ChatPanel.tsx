import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, X, Maximize2, Minimize2, ChevronDown, Paperclip, MessageSquarePlus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/contexts/ChatContext";
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
    startNewChat,
    chatReady,
  } = useChat();
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

  const handleSend = () => {
    const text = input.trim();
    if (!text && !selectedFile) return;
    if (isSending) return; // Block duplicate sends
    setInput("");
    void send(text || "Please consider attached file.", selectedFile ? { name: selectedFile.name, size: selectedFile.size } : null);
    setSelectedFile(null);
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

        <div className="border-t border-border bg-card px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Quick actions</p>
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
            <button
              onClick={handleSend}
              disabled={(!input.trim() && !selectedFile) || !chatReady || isSending || isTyping}
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
