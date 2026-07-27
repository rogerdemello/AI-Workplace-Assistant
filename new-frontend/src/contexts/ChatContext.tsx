import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";
import {
  closeConversation,
  fetchMemoryCards,
  fetchPendingNudges,
  requestChatReply,
  startChatSession,
  submitChatCsat,
  type ChatAttachmentMeta,
} from "@/lib/chat-api";
import { mapFlowMetadataToControl } from "@/lib/flow-metadata-ui";
import { loadChatSnapshot, saveChatSnapshot } from "@/lib/chat-session-storage";
import { logMyMood } from "@/lib/api/portal";
import { subscribeToSse } from "@/lib/api/client";
import type { ChatRecord, ControlState, FlowMetadata, MemoryCard } from "@/types/chat";

export type MoodChoice = { emoji: "🙂" | "😐" | "😟" | "😔"; score: number; label: string };

export const MOOD_CHOICES: MoodChoice[] = [
  { emoji: "🙂", score: 80, label: "Good" },
  { emoji: "😐", score: 55, label: "Okay" },
  { emoji: "😟", score: 35, label: "Meh" },
  { emoji: "😔", score: 15, label: "Low" },
];

const MOOD_ACKS: Record<string, string> = {
  "🙂": "Love to hear it 😊 What's on your plate today?",
  "😐": "Got it — a steady kind of day. I'm here if anything comes up.",
  "😟": "Thanks for being honest. Want to talk about what's weighing on you?",
  "😔": "I'm sorry it's a rough one 💙 I'm here — want to share what's going on?",
};

export type ChatMode = "minimized" | "panel" | "full";

interface ChatContextValue {
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  open: () => void;
  toggle: () => void;
  expand: () => void;
  minimize: () => void;
  messages: ChatRecord[];
  isTyping: boolean;
  isSending: boolean;
  control: ControlState;
  flowMetadata: FlowMetadata | null;
  memoryCards: MemoryCard[];
  quickActions: string[];
  send: (text: string, attachment?: ChatAttachmentMeta | null) => Promise<void>;
  onControlAction: (value: string) => Promise<void>;
  onDateAction: (value: string) => Promise<void>;
  pendingCsat: boolean;
  submitCsatRating: (rating: number) => Promise<void>;
  dismissCsat: () => void;
  /** True when the daily greeting invited a mood check-in; renders mood chips. */
  moodCheckinActive: boolean;
  logMoodCheckin: (choice: MoodChoice) => Promise<void>;
  dismissMoodCheckin: () => void;
  /** Clear local thread, persist a fresh snapshot, and best-effort close the server conversation. */
  startNewChat: () => void;
  unreadCount: number;
  /** Employee chat: false until server conversation + proactive greeting are loaded (avoids duplicate /start). */
  chatReady: boolean;
  /** Active backend conversation id, when known — used to ground downstream actions (e.g. "draft an email about this") in the current chat. */
  conversationId: string | null;
}

const ChatContext = createContext<ChatContextValue | null>(null);

const shortId = () => Math.random().toString(36).slice(2, 9);
const firstName = (name?: string) => (name?.trim().split(/\s+/)[0] || "there");
const defaultControl = (): ControlState => ({ kind: null });
const CSAT_COOLDOWN_MS = 8 * 60 * 1000;
const ACTIVE_WINDOW_MS = 30 * 60 * 1000;
export function ChatProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [mode, setMode] = useState<ChatMode>("minimized");
  const [messages, setMessages] = useState<ChatRecord[]>([]);
  const [chatReady, setChatReady] = useState(() => true);
  const [control, setControl] = useState<ControlState>(defaultControl());
  const [flowMetadata, setFlowMetadata] = useState<FlowMetadata | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [memoryCards, setMemoryCards] = useState<MemoryCard[]>([]);
  const [moodCheckinActive, setMoodCheckinActive] = useState(false);
  const [pendingCsatMeta, setPendingCsatMeta] = useState<{ conversationId?: string; intent?: string; sentiment?: string } | null>(null);
  const hydratedRef = useRef(false);
  const lastActivityRef = useRef(Date.now());
  const lastCsatAtRef = useRef(0);
  const breakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const secondBreakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSentAtRef = useRef(0);

  /** Append a proactive message unless that exact text is already on screen.
   *
   *  Deduping on content is what lets the catch-up fetch be safely idempotent:
   *  a nudge delivered live over SSE and then returned again by the fetch shows
   *  once, and one that never rendered still gets a second chance. */
  const appendAssistantIfNew = useCallback((text: string) => {
    setMessages((current) =>
      current.some((m) => m.role === "assistant" && m.text === text)
        ? current
        : [...current, { id: shortId(), role: "assistant", text }],
    );
  }, []);

  const appendAssistant = useCallback((text: string) => {
    setMessages((current) => [...current, { id: shortId(), role: "assistant", text }]);
    setMode((currentMode) => {
      if (currentMode === "minimized") {
        setUnreadCount((count) => count + 1);
      }
      return currentMode;
    });
  }, []);

  const logMoodCheckin = useCallback(
    async (choice: MoodChoice) => {
      setMoodCheckinActive(false);
      // Echo the user's pick into the thread so the conversation reads naturally.
      setMessages((current) => [
        ...current,
        { id: shortId(), role: "user", text: `${choice.emoji} ${choice.label}` },
      ]);
      const ok = await logMyMood({ moodEmoji: choice.emoji, moodScore: choice.score });
      if (!ok) {
        appendAssistant("I couldn't save that just now, but I'm still here. What's up?");
        return;
      }
      appendAssistant(MOOD_ACKS[choice.emoji] ?? "Thanks for checking in 💙 What's on your mind?");
    },
    [appendAssistant],
  );

  const dismissMoodCheckin = useCallback(() => setMoodCheckinActive(false), []);

  const createAssistantStreamTarget = useCallback(() => {
    const id = shortId();
    setMessages((current) => [...current, { id, role: "assistant", text: "" }]);
    setMode((currentMode) => {
      if (currentMode === "minimized") {
        setUnreadCount((count) => count + 1);
      }
      return currentMode;
    });
    return {
      set: (text: string) => {
        setMessages((current) => current.map((item) => (item.id === id ? { ...item, text } : item)));
      },
    };
  }, []);

  useEffect(() => {
    if (!session?.email) {
      return;
    }
    let cancelled = false;
    hydratedRef.current = false;
    setChatReady(session.role !== "employee");

    const snapshot = loadChatSnapshot(session.email);

    if (session.role !== "employee") {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          text: `Hi ${firstName(session.name)} — I'm MARK. Open this chat anytime for HR support.`,
        },
      ]);
      setConversationId(null);
      setFlowMetadata(null);
      setControl(defaultControl());
      setPendingCsatMeta(null);
      setMoodCheckinActive(false);
      hydratedRef.current = true;
      return () => {
        cancelled = true;
      };
    }

    if (snapshot?.messages.length) {
      setMessages(snapshot.messages);
      setConversationId(snapshot.conversationId ?? null);
      const fm = snapshot.flowMetadata ?? null;
      setFlowMetadata(fm);
      setControl(mapFlowMetadataToControl(fm));
      setPendingCsatMeta(null);
      setMoodCheckinActive(false);
      hydratedRef.current = true;
      setChatReady(true);
      return () => {
        cancelled = true;
      };
    }

    void startChatSession(session).then((started) => {
      if (cancelled) {
        return;
      }
      if (started) {
        setMessages([{ id: "open", role: "assistant", text: started.greeting }]);
        setConversationId(started.conversationId);
        setMoodCheckinActive(Boolean(started.suggestedMoodCheckin));
      } else {
        setMessages([
          {
            id: "welcome",
            role: "assistant",
            text: `Hi ${firstName(session.name)}. I could not reach the chat server — check that you are signed in and the API is running.`,
          },
        ]);
        setConversationId(null);
      }
      setFlowMetadata(null);
      setControl(defaultControl());
      setPendingCsatMeta(null);
      hydratedRef.current = true;
      setChatReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [session?.email, session?.name, session?.role]);

  useEffect(() => {
    if (!hydratedRef.current || !session?.email) return;
    const timer = setTimeout(() => {
      saveChatSnapshot(session.email, { messages, conversationId, flowMetadata });
    }, 250);
    return () => clearTimeout(timer);
  }, [messages, conversationId, flowMetadata, session?.email]);

  // Live proactive nudges: employees subscribe to their per-user SSE stream so
  // a break reminder / scheduled reminder lands in the open chat immediately
  // instead of waiting for the next polling cycle.
  useEffect(() => {
    if (!session?.email || session.role !== "employee") return;
    const unsubscribe = subscribeToSse("/api/v1/realtime/me/stream", {
      onEvent: (eventType, payload) => {
        if (eventType !== "user_nudge") return;
        const text = typeof payload.message === "string" ? payload.message.trim() : "";
        // Deliberately does NOT advance the watermark. That was keyed on
        // wall-clock "now", so one live nudge marked every earlier one as seen
        // — and if this message did not survive in state, the catch-up fetch
        // could never recover it. Dedupe by content instead.
        if (text) appendAssistantIfNew(text);
      },
    });
    return unsubscribe;
  }, [session?.email, session?.role, appendAssistantIfNew]);

  // Catch-up: check-ins sent while this client was closed. SSE only reaches an
  // open tab and the transcript is restored from local storage, so without this
  // a nudge to an away employee — the whole point of the feature — is never seen.
  useEffect(() => {
    if (!session?.email || session.role !== "employee" || !chatReady) return;
    let cancelled = false;

    // No client-side watermark. The transcript lives in local storage and can
    // be cleared, replaced, or simply not saved before a reload — so anything
    // that marks a nudge "seen" independently of the transcript will eventually
    // suppress a message the employee never actually read. Re-fetching the
    // recent window every time and deduping by content is idempotent, and
    // errs toward showing an HR message twice rather than losing it.
    void fetchPendingNudges(session, null).then((nudges) => {
      if (cancelled || nudges.length === 0) return;
      nudges.forEach((nudge) => {
        if (nudge.text.trim()) appendAssistantIfNew(nudge.text);
      });
    });

    return () => {
      cancelled = true;
    };
  }, [session?.email, session?.role, chatReady, appendAssistantIfNew]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const markActivity = () => {
      lastActivityRef.current = Date.now();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        lastActivityRef.current = Date.now();
      }
    };
    window.addEventListener("pointerdown", markActivity);
    window.addEventListener("keydown", markActivity);
    window.addEventListener("focus", markActivity);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pointerdown", markActivity);
      window.removeEventListener("keydown", markActivity);
      window.removeEventListener("focus", markActivity);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    if (!session?.email) return;
    let active = true;
    void fetchMemoryCards(session, 3).then((cards) => {
      if (!active) return;
      setMemoryCards(
        cards
          .map((card) => ({
            title: String(card.title ?? "Recent memory"),
            summary: String(card.summary ?? ""),
            tags: Array.isArray(card.tags) ? card.tags.map((tag) => String(tag)) : [],
            lastUpdated: String(card.last_updated ?? ""),
          }))
          .filter((card) => card.summary.trim().length > 0),
      );
    });
    return () => {
      active = false;
    };
  }, [session?.email]);

  const send = useCallback(
    async (text: string, attachment?: ChatAttachmentMeta | null) => {
      const trimmed = text.trim();
      if (!trimmed && !attachment) return;
      if (session?.role === "employee" && !chatReady) {
        return;
      }
      
      // CRITICAL FIX: Prevent duplicate sends - lock while sending
      if (isSending) {
        console.warn("[Chat] Message blocked: already sending");
        return;
      }
      
      // Debounce: prevent rapid-fire sends within 500ms
      const now = Date.now();
      if (now - lastSentAtRef.current < 500) {
        console.warn("[Chat] Message blocked: debounce");
        return;
      }
      lastSentAtRef.current = now;
      setIsSending(true);
      
      lastActivityRef.current = Date.now();
      setMessages((current) => [...current, { id: shortId(), role: "user", text: trimmed || "(attachment)" }]);
      setIsTyping(true);
      setPendingCsatMeta(null);

      try {
        const streamTarget = createAssistantStreamTarget();
        const reply = await requestChatReply(
          { message: trimmed || "Please see attached file.", conversationId: conversationId ?? undefined, attachment },
          session,
          { onPartial: (text) => streamTarget.set(text) },
        );

        if (reply?.reply) {
          streamTarget.set(reply.reply);

          const cid = reply.state.conversationId ?? conversationId;
          setConversationId(cid ?? null);

          const fm = reply.state.flowMetadata ?? null;
          setFlowMetadata(fm);
          setControl(mapFlowMetadataToControl(fm));

          const flowDone = Boolean(reply.state.completed || fm?.completed);
          if (flowDone && fm?.flow_name) {
            const now = Date.now();
            if (now - lastCsatAtRef.current > CSAT_COOLDOWN_MS) {
              setPendingCsatMeta({
                conversationId: cid,
                intent: reply.state.intent,
                sentiment: reply.state.sentiment,
              });
              lastCsatAtRef.current = now;
            }
          }
        } else {
          streamTarget.set(
            "I couldn't reach MARK just now — often this is a stale chat session after a DB reset or new login. Refresh the page, then send your message again.",
          );
          setFlowMetadata(null);
          setControl(defaultControl());
        }
      } finally {
        setIsTyping(false);
        setIsSending(false);
      }
    },
    [appendAssistant, chatReady, conversationId, createAssistantStreamTarget, session, isSending],
  );

  const onControlAction = useCallback(
    async (value: string) => {
      lastActivityRef.current = Date.now();
      await send(value);
    },
    [send],
  );

  const onDateAction = useCallback(
    async (value: string) => {
      lastActivityRef.current = Date.now();
      await send(value);
    },
    [send],
  );

  const open = useCallback(() => {
    setMode("panel");
    setUnreadCount(0);
  }, []);
  const toggle = useCallback(() => setMode((current) => (current === "minimized" ? "panel" : "minimized")), []);
  const expand = useCallback(() => setMode("full"), []);
  const minimize = useCallback(() => setMode("minimized"), []);

  const quickActions = useMemo(() => {
    const fm = flowMetadata;
    if (fm?.flow_name && !fm.completed) {
      if (fm.flow_name === "leave_request" && fm.step === "leave_type") {
        return ["paid", "sick", "work from home", "unpaid"];
      }
      if (fm.flow_name === "ticket" && fm.step === "severity") {
        return ["mild", "serious", "urgent"];
      }
    }
    const lastUserMessage = [...messages].reverse().find((item) => item.role === "user")?.text.toLowerCase() || "";
    if (/\b(stress|burnout|anxious|tired)\b/.test(lastUserMessage)) {
      return ["Take 5-minute reset", "Raise confidential ticket", "Talk through it"];
    }
    return ["Apply leave", "Raise complaint", "Ask policy"];
  }, [flowMetadata, messages]);

  useEffect(() => {
    if (breakTimerRef.current) {
      clearTimeout(breakTimerRef.current);
      breakTimerRef.current = null;
    }
    if (secondBreakTimerRef.current) {
      clearTimeout(secondBreakTimerRef.current);
      secondBreakTimerRef.current = null;
    }
    if (!session?.email || session.role !== "employee") {
      return;
    }

    const loginAt = session.loginAtMs ?? Date.now();
    const firstAt = session.breakReminderAtMs ?? loginAt + 2 * 60 * 60 * 1000;
    const secondAt = session.secondBreakReminderAtMs ?? loginAt + Math.round(5.5 * 60 * 60 * 1000);

    const maybeSendSecondReminder = () => {
      const now = Date.now();
      const isActive =
        now - lastActivityRef.current <= ACTIVE_WINDOW_MS && (typeof document === "undefined" || document.visibilityState === "visible");
      if (isActive) {
        appendAssistant(
          `One more friendly nudge, ${firstName(session.name)}: it has been around a few hours. If you can, take a proper 10-minute breather.`,
        );
      } else if (now < secondAt + 60 * 60 * 1000) {
        secondBreakTimerRef.current = setTimeout(maybeSendSecondReminder, 15 * 60 * 1000);
      }
    };

    const now = Date.now();
    const firstDelay = firstAt - now;
    if (firstDelay <= 0) {
      appendAssistant(`Hey ${firstName(session.name)}, quick reminder to stretch and grab some water.`);
    } else {
      breakTimerRef.current = setTimeout(() => {
        appendAssistant(`Hey ${firstName(session.name)}, quick reminder to stretch and grab some water.`);
      }, firstDelay);
    }

    const secondDelay = secondAt - now;
    if (secondDelay <= 0) {
      maybeSendSecondReminder();
    } else {
      secondBreakTimerRef.current = setTimeout(maybeSendSecondReminder, secondDelay);
    }

    return () => {
      if (breakTimerRef.current) clearTimeout(breakTimerRef.current);
      if (secondBreakTimerRef.current) clearTimeout(secondBreakTimerRef.current);
    };
  }, [appendAssistant, session?.breakReminderAtMs, session?.email, session?.loginAtMs, session?.name, session?.role, session?.secondBreakReminderAtMs]);

  const submitCsatRating = useCallback(
    async (rating: number) => {
      if (!pendingCsatMeta) return;
      await submitChatCsat(
        {
          rating,
          conversationId: pendingCsatMeta.conversationId,
          intent: pendingCsatMeta.intent,
          sentiment: pendingCsatMeta.sentiment,
        },
        session,
      );
      setPendingCsatMeta(null);
    },
    [pendingCsatMeta, session],
  );

  const dismissCsat = useCallback(() => {
    setPendingCsatMeta(null);
  }, []);

  const startNewChat = useCallback(() => {
    const previousId = conversationId;
    setIsTyping(false);
    setPendingCsatMeta(null);
    setFlowMetadata(null);
    setControl(defaultControl());
    if (previousId) {
      void closeConversation(previousId, session);
    }

    if (session?.role === "employee") {
      setChatReady(false);
      void startChatSession(session).then((started) => {
        if (started) {
          const welcome: ChatRecord[] = [{ id: "open", role: "assistant", text: started.greeting }];
          setConversationId(started.conversationId);
          setMessages(welcome);
          if (session.email) {
            saveChatSnapshot(session.email, { messages: welcome, conversationId: started.conversationId, flowMetadata: null });
          }
        } else {
          const welcome: ChatRecord[] = [
            {
              id: "welcome",
              role: "assistant",
              text: session?.name
                ? `Hey ${firstName(session.name)} — I'm Mark. I could not start a new server thread; try again shortly.`
                : "Hey — I'm Mark. I could not start a new server thread; try again shortly.",
            },
          ];
          setConversationId(null);
          setMessages(welcome);
          if (session.email) {
            saveChatSnapshot(session.email, { messages: welcome, conversationId: null, flowMetadata: null });
          }
        }
        setChatReady(true);
      });
      return;
    }

    const welcome: ChatRecord[] = [
      {
        id: "welcome",
        role: "assistant",
        text: session?.name
          ? `Hi ${firstName(session.name)} — I'm MARK. What do you need?`
          : "Hi — I'm MARK. What do you need?",
      },
    ];
    setConversationId(null);
    setMessages(welcome);
    if (session?.email) {
      saveChatSnapshot(session.email, { messages: welcome, conversationId: null, flowMetadata: null });
    }
  }, [conversationId, session]);

  return (
    <ChatContext.Provider
      value={{
        mode,
        setMode,
        open,
        toggle,
        expand,
        minimize,
        messages,
        isTyping,
        isSending,
        control,
        flowMetadata,
        memoryCards,
        quickActions,
        send,
        onControlAction,
        onDateAction,
        pendingCsat: Boolean(pendingCsatMeta),
        submitCsatRating,
        dismissCsat,
        moodCheckinActive,
        logMoodCheckin,
        dismissMoodCheckin,
        startNewChat,
        unreadCount,
        chatReady,
        conversationId,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) throw new Error("useChat must be used within ChatProvider");
  return context;
}
