import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";
import {
  closeConversation,
  fetchMemoryCards,
  requestChatReply,
  startChatSession,
  submitChatCsat,
  type ChatAttachmentMeta,
} from "@/lib/chat-api";
import { mapFlowMetadataToControl } from "@/lib/flow-metadata-ui";
import { loadChatSnapshot, saveChatSnapshot } from "@/lib/chat-session-storage";
import type { ChatRecord, ControlState, FlowMetadata, MemoryCard } from "@/types/chat";

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
  /** Clear local thread, persist a fresh snapshot, and best-effort close the server conversation. */
  startNewChat: () => void;
  unreadCount: number;
  /** Employee chat: false until server conversation + proactive greeting are loaded (avoids duplicate /start). */
  chatReady: boolean;
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
  const [pendingCsatMeta, setPendingCsatMeta] = useState<{ conversationId?: string; intent?: string; sentiment?: string } | null>(null);
  const hydratedRef = useRef(false);
  const lastActivityRef = useRef(Date.now());
  const lastCsatAtRef = useRef(0);
  const breakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const secondBreakTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSentAtRef = useRef(0);

  const appendAssistant = useCallback((text: string) => {
    setMessages((current) => [...current, { id: shortId(), role: "assistant", text }]);
    setMode((currentMode) => {
      if (currentMode === "minimized") {
        setUnreadCount((count) => count + 1);
      }
      return currentMode;
    });
  }, []);

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
        startNewChat,
        unreadCount,
        chatReady,
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
