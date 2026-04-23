"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Calendar, MessageSquare, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatInput, type SelectedFile } from '@/components/ChatInput';
import { ChatMessage } from '@/components/ChatMessage';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { persistChatMessage } from '@/lib/hr-data';
import { loadChatSnapshot, saveChatSnapshot } from '@/lib/chat-session-storage';
import type { ChatRecord, ControlState, FlowState, Intent } from '@/types/employee-chat';
import { patchSession, type AppSession } from '@/lib/session';
import { cn } from '@/lib/utils';
import {
  createWellbeingReminder,
  submitDailyCheckin,
  type DailyCheckinMood,
  type WellbeingScheduleKind,
} from '@/lib/api';

const departmentOptions = ['Engineering', 'Sales', 'Marketing', 'People Ops', 'Finance', 'IT'];
const leaveTypeOptions = ['Paid leave', 'Sick leave', 'Work from home'];
const policyOptions = ['Leave policy', 'Payroll', 'Benefits', 'Remote work'];
const primaryIntentActions = ['Apply leave', 'Raise complaint', 'Ask policy'];
const stressSupportActions = ['Take 5-minute reset', 'Raise confidential ticket', 'Talk through it'];
const leaveSupportActions = ['Apply leave', 'Leave policy', 'Draft manager note'];
const hrSupportActions = ['Raise complaint', 'Ask policy', 'Talk to HR'];
const FIRST_BREAK_REMINDER_DELAY_MS = 2 * 60 * 60 * 1000;
const SECOND_BREAK_REMINDER_FALLBACK_DELAY_MS = Math.round(5.5 * 60 * 60 * 1000);
const ACTIVE_WINDOW_MS = 45 * 60 * 1000;
const BACKEND_QUICK_TIMEOUT_MS = 2400;
const CSAT_COOLDOWN_MS = 8 * 60 * 1000;
const ENABLE_CSAT_PROMPT = false;
const AUTO_CHECKIN_COOLDOWN_MS = 6 * 60 * 60 * 1000;
const AUTO_REMINDER_DEDUPE_MS = 2 * 60 * 1000;

interface MemoryCard {
  title: string;
  summary: string;
  tags: string[];
  lastUpdated: string;
}

interface PendingCsat {
  conversationId?: string;
  intent?: string;
  sentiment?: string;
  askedAt: number;
}

interface InferredReminder {
  reminderType: string;
  title: string;
  message: string;
  scheduleKind: WellbeingScheduleKind;
  runAtIso?: string;
  humanSchedule: string;
}

function firstNameFromSession(session: AppSession | null): string {
  const firstToken = session?.name?.trim().split(/\s+/)[0];
  return firstToken && firstToken.length > 0 ? firstToken : 'there';
}

function loginGreetingText(session: AppSession | null): string {
  const firstName = firstNameFromSession(session);
  return `Hey ${firstName}! I'm Mark. How are you doing today, and how's your day going so far?`;
}

function formatElapsed(ms: number): string {
  const totalMinutes = Math.max(1, Math.round(ms / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${totalMinutes} minutes`;
  }

  if (minutes === 0) {
    return `${hours} hour${hours === 1 ? '' : 's'}`;
  }

  return `${hours} hour${hours === 1 ? '' : 's'} ${minutes} min`;
}

function breakReminderText(session: AppSession | null, loginAtMs: number, nowMs: number): string {
  const firstName = firstNameFromSession(session);
  const elapsed = formatElapsed(Math.max(0, nowMs - loginAtMs));
  return `Hey ${firstName}, you've been online for about ${elapsed}. Quick nudge to take a short break, stretch, and grab some water.`;
}

function secondBreakReminderText(session: AppSession | null, loginAtMs: number, nowMs: number): string {
  const firstName = firstNameFromSession(session);
  const elapsed = formatElapsed(Math.max(0, nowMs - loginAtMs));
  return `One more friendly nudge, ${firstName}: it's been around ${elapsed}. If you can, take a proper 10-minute breather.`;
}

function initialAssistantMessage(session: AppSession | null): ChatRecord {
  return {
    id: 'welcome',
    role: 'assistant',
    text: loginGreetingText(session),
  };
}

/** User wants to formalize / escalate to HR (complaint flow). */
function wantsHrTicket(message: string): boolean {
  const v = message.toLowerCase();
  return (
    /\braise\s+(a\s+)?ticket\b/.test(v) ||
    /\b(open|file|submit)\s+(a\s+)?(ticket|complaint)\b/.test(v) ||
    /\bticket\s+to\s+hr\b/.test(v) ||
    /\bescalate\b/.test(v) ||
    v.includes('raise it') ||
    (v.includes('ticket') && (v.includes('hr') || v.includes('human resources')))
  );
}

/** Enough context to route to HR without asking the employee to repeat themselves. */
function complaintDetailIsSufficient(combinedIssue: string, lastMessage: string): boolean {
  if (wantsHrTicket(lastMessage)) {
    return true;
  }
  const t = combinedIssue.trim();
  const strongComplaintSignal =
    /\b(manager|supervisor|lead|harass|bully|payroll|policy|leave|credit|stress|toxic|unfair|discriminat|complaint|hr)\b/i.test(
      t
    );

  if (t.length >= 52) {
    return true;
  }
  // Even short messages should proceed when intent is clearly complaint-like.
  if (strongComplaintSignal && t.length >= 10) {
    return true;
  }
  if (t.length < 18) {
    return false;
  }
  return /\b(manager|supervisor|lead|credit|workplace|harass|bully|payroll|policy|leave|team|project|present|ignored|backfoot|complaint|hr\b|unfair|discriminat|stress|toxic)/i.test(
    t
  );
}

function inferIntent(message: string): Intent {
  const value = message.toLowerCase();

  const isPolicyLike =
    value.includes('policy') ||
    value.includes('handbook') ||
    value.includes('benefit') ||
    value.includes('how do') ||
    /\b(remote work|payroll|leave policy)\b/.test(value);

  // "How many leaves are left" should not start a leave-application wizard.
  const asksLeaveBalance =
    /\b(how many|how much|remaining|left|balance)\b/.test(value) &&
    /\b(leave|leaves|pto|vacation|time off)\b/.test(value);

  if (
    value.includes('complaint') ||
    value.includes('harassment') ||
    value.includes('issue') ||
    value.includes('problem') ||
    value.includes('payroll') ||
    value.includes('manager') ||
    wantsHrTicket(message)
  ) {
    return 'complaint';
  }

  if (isPolicyLike || asksLeaveBalance) {
    return 'policy';
  }

  if (value.includes('leave') || value.includes('vacation') || value.includes('pto') || value.includes('time off')) {
    return 'leave';
  }

  return 'general';
}

function isLeaveBalanceQuestion(message: string): boolean {
  const value = message.toLowerCase();
  return (
    /\b(how many|how much|remaining|left|balance)\b/.test(value) &&
    /\b(leave|leaves|pto|vacation|time off)\b/.test(value)
  );
}

function shortId(): string {
  return Math.random().toString(36).slice(2, 9);
}

function humanDate(value: string): string {
  if (!value) return '';
  return new Date(`${value}T09:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function intentFromAction(action: string): Intent {
  const value = action.toLowerCase();
  if (value.includes('leave')) return 'leave';
  if (value.includes('ticket') || value.includes('hr')) return 'complaint';
  if (value.includes('complaint')) return 'complaint';
  if (value.includes('policy')) return 'policy';
  return 'general';
}

function detectDepartment(text: string): string | null {
  const normalized = text.trim().toLowerCase();
  const match = departmentOptions.find((d) => d.toLowerCase() === normalized);
  return match ?? null;
}

function hasStressSignal(message: string): boolean {
  return /\b(stress|stressed|burnout|burned out|overwhelm|anxious|anxiety|exhaust|tired|drained|panic)\b/.test(message);
}

function hasHrIssueSignal(message: string): boolean {
  return /\b(manager|harass|bully|toxic|unfair|credit|complaint|hr|escalat|ignored|pressure)\b/.test(message);
}

function inferDailyMood(message: string): DailyCheckinMood | null {
  const value = message.toLowerCase();

  const hasMoodContext = /\b(i am|i'm|i feel|feeling|today|right now|mentally|emotionally)\b/.test(value);
  const hasStrongSignal = /\b(stressed|stress|overwhelmed|burnout|burned out|anxious|anxiety|panic|drained|exhausted|tired|low|sad|upset|good|great|happy)\b/.test(value);

  if (!hasMoodContext && !hasStrongSignal) {
    return null;
  }

  if (/\b(stressed|stress|overwhelmed|burnout|burned out|anxious|anxiety|panic)\b/.test(value)) {
    return 'stressed';
  }

  if (/\b(drained|exhausted|tired|low|sad|upset|rough day)\b/.test(value)) {
    return 'low';
  }

  if (/\b(great|awesome|amazing|happy|excellent)\b/.test(value)) {
    return 'great';
  }

  if (/\b(good|fine|better|okay|ok|alright|all right)\b/.test(value)) {
    return 'good';
  }

  return 'okay';
}

function parseNaturalRunAt(message: string): Date | null {
  const lower = message.toLowerCase();
  const now = new Date();

  let base = new Date(now);
  let hasExplicitDate = false;

  const isoDate = lower.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);
  if (isoDate) {
    base = new Date(Number(isoDate[1]), Number(isoDate[2]) - 1, Number(isoDate[3]));
    hasExplicitDate = true;
  } else {
    const usDate = lower.match(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/);
    if (usDate) {
      const year = usDate[3]
        ? Number(usDate[3].length === 2 ? `20${usDate[3]}` : usDate[3])
        : now.getFullYear();
      base = new Date(year, Number(usDate[1]) - 1, Number(usDate[2]));
      hasExplicitDate = true;
    } else if (lower.includes('tomorrow')) {
      base.setDate(base.getDate() + 1);
      hasExplicitDate = true;
    }
  }

  let hours = 9;
  let minutes = 0;
  let hasTime = false;

  const twelveHour = lower.match(/\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/);
  if (twelveHour) {
    const rawHour = Number(twelveHour[1]);
    const ampm = twelveHour[3];
    hours = rawHour % 12;
    if (ampm === 'pm') hours += 12;
    minutes = twelveHour[2] ? Number(twelveHour[2]) : 0;
    hasTime = true;
  } else {
    const twentyFour = lower.match(/\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b/);
    if (twentyFour) {
      hours = Number(twentyFour[1]);
      minutes = Number(twentyFour[2]);
      hasTime = true;
    }
  }

  if (!hasExplicitDate && !hasTime) {
    return null;
  }

  base.setHours(hours, minutes, 0, 0);

  if (!hasExplicitDate && base.getTime() <= now.getTime() + 2 * 60 * 1000) {
    base.setDate(base.getDate() + 1);
  }

  return base;
}

function cleanReminderTitle(rawTask: string): string {
  const cleaned = rawTask
    .replace(/\b(today|tomorrow|daily|every day|weekly|every week)\b/gi, ' ')
    .replace(/\b(?:at\s+)?(\d{1,2})(?::\d{2})?\s*(am|pm)\b/gi, ' ')
    .replace(/\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b/gi, ' ')
    .replace(/\bon\s+\d{4}-\d{2}-\d{2}\b/gi, ' ')
    .replace(/\bon\s+\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/gi, ' ')
    .replace(/[.,;:!?]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleaned) {
    return 'Reminder';
  }

  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function inferReminderFromMessage(message: string): InferredReminder | null {
  const lower = message.toLowerCase();
  if (!/(\bremind me\b|\bset (?:a )?reminder\b)/.test(lower)) {
    return null;
  }

  const actionMatch = message.match(/(?:remind me to|set (?:a )?reminder(?: to)?)(.*)$/i);
  const rawTask = (actionMatch?.[1] ?? 'follow up').trim();

  let scheduleKind: WellbeingScheduleKind = 'one_time';
  if (/\b(daily|every day|each day)\b/i.test(message)) {
    scheduleKind = 'daily';
  } else if (/\b(weekly|every week|each week)\b/i.test(message)) {
    scheduleKind = 'weekly';
  }

  const parsedRunAt = parseNaturalRunAt(message);
  const fallbackRunAt = new Date(Date.now() + 60 * 60 * 1000);
  const runAt = scheduleKind === 'one_time' ? (parsedRunAt ?? fallbackRunAt) : parsedRunAt;

  const reminderType = /\b(medicine|tablet|pill|medication)\b/i.test(message)
    ? 'medicine'
    : /\b(break|stretch|water|hydrate)\b/i.test(message)
      ? 'break'
      : /\b(meeting|call|standup|sync)\b/i.test(message)
        ? 'meeting'
        : 'custom';

  const title = cleanReminderTitle(rawTask);
  const reminderMessage = `Reminder: ${title}`;

  const humanSchedule = runAt
    ? scheduleKind === 'daily'
      ? `daily around ${runAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
      : scheduleKind === 'weekly'
        ? `weekly around ${runAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
        : runAt.toLocaleString()
    : scheduleKind;

  return {
    reminderType,
    title,
    message: reminderMessage,
    scheduleKind,
    runAtIso: runAt ? runAt.toISOString() : undefined,
    humanSchedule,
  };
}

function contextualQuickActions(lastUserMessage: string): string[] {
  const value = lastUserMessage.toLowerCase();

  if (hasStressSignal(value)) {
    return stressSupportActions;
  }

  if (/\b(leave|vacation|pto|time off|sick)\b/.test(value)) {
    return leaveSupportActions;
  }

  if (/\b(policy|benefit|payroll|salary|remote work|handbook)\b/.test(value) || hasHrIssueSignal(value)) {
    return hrSupportActions;
  }

  return primaryIntentActions;
}

async function askBackend(
  message: string,
  state: Partial<FlowState>,
  session: AppSession | null,
  file?: SelectedFile | null,
  timeoutMs: number = BACKEND_QUICK_TIMEOUT_MS
) {
  const effectiveTimeoutMs = file?.file ? Math.max(timeoutMs, 6000) : timeoutMs;
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), effectiveTimeoutMs) : null;

  try {
    const authToken =
      typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

    if (file?.file) {
      const formData = new FormData();
      formData.append('message', message);
      formData.append('file', file.file);
      formData.append('fileName', file.name);
      if (state) formData.append('state', JSON.stringify(state));
      if (session?.email) formData.append('userEmail', session.email);
      if (session?.name) formData.append('userName', session.name);
      if (session?.role) formData.append('userRole', session.role);
      if (authToken) formData.append('authToken', authToken);

      const response = await fetch('/api/chat', {
        method: 'POST',
        body: formData,
        signal: controller?.signal,
      });

      if (!response.ok) {
        return null;
      }

      return (await response.json()) as { reply?: string; state?: Partial<FlowState> };
    }

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        state,
        userEmail: session?.email,
        userName: session?.name,
        userRole: session?.role,
        ...(authToken ? { authToken } : {}),
      }),
      signal: controller?.signal,
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as { reply?: string; state?: Partial<FlowState> };
  } catch {
    return null;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

function assistantReplyForGeneral(message: string): string {
  const value = message.toLowerCase().trim();

  if (/\b(hi|hey|hello|yo|sup|what's up)\b/.test(value)) {
    return "Hey! Good to see you. Tell me what's on your mind and we'll sort it out together.";
  }

  if (/\b(how are you|how's your day|hows your day)\b/.test(value)) {
    return "I'm doing well, thanks for asking. How are you feeling right now?";
  }

  if (/\b(thanks|thank you|thx|appreciate it)\b/.test(value)) {
    return 'Anytime. I am right here if you want to keep going.';
  }

  if (hasStressSignal(value)) {
    return 'That sounds heavy. Want a quick 5-minute reset, or should I help you raise this confidentially?';
  }

  if (value.includes('policy')) {
    return 'Yep, I can check that policy for you. Which one should I pull up?';
  }

  if (value.includes('benefit') || value.includes('payroll') || value.includes('salary')) {
    return 'Got you. Want me to explain benefits, payroll, or the related policy first?';
  }

  if (hasHrIssueSignal(value)) {
    return 'I hear you. If you want, I can raise this with HR confidentially in a couple of quick steps.';
  }

  return 'I got you. Want me to raise this as a ticket, or should we keep chatting and sort it out here?';
}

async function createTicketFromChat(
  input: {
    category: 'leave' | 'complaint' | 'policy' | 'general';
    query: string;
    priority?: 'low' | 'medium' | 'high' | 'critical';
  },
  session: AppSession | null
): Promise<string | null> {
  try {
    const authToken =
      typeof window !== 'undefined' ? window.localStorage.getItem('auth_token') : null;
    const response = await fetch('/api/chat/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...input,
        userEmail: session?.email,
        userName: session?.name,
        ...(authToken ? { authToken } : {}),
      }),
    });

    if (!response.ok) {
      return null;
    }

    const data = (await response.json()) as { id?: string };
    return data.id ?? null;
  } catch {
    return null;
  }
}

/** RAG-first policy answer via Next route → FastAPI `/rag/search-with-answer`, with graceful fallback copy. */
async function fetchPolicyRagAnswer(topic: string, session: AppSession | null): Promise<string> {
  try {
    const authToken = typeof window !== 'undefined' ? window.localStorage.getItem('auth_token') : null;
    const res = await fetch('/api/chat/policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        userEmail: session?.email,
        userName: session?.name,
        ...(authToken ? { authToken } : {}),
      }),
    });
    const data = (await res.json()) as { answer?: string };
    if (!res.ok) {
      return `I could not reach the policy knowledge base right now. For “${topic}”, please check with HR or try again shortly.`;
    }
    return (
      data.answer?.trim() ||
      `I do not have retrieved policy text for “${topic}” in the knowledge base yet. HR can confirm the official wording.`
    );
  } catch {
    return `Something went wrong while looking up “${topic}”. Please contact HR for the official policy.`;
  }
}

interface CrossTabMessage {
  type: 'mark:greeted' | 'mark:nudged';
  nudgeType?: string;
}

let crossTabChannel: BroadcastChannel | null = null;

function getCrossTabChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') {
    return null;
  }
  if (!crossTabChannel) {
    crossTabChannel = new BroadcastChannel('mark-cross-tab');
  }
  return crossTabChannel;
}

function broadcastCrossTab(message: CrossTabMessage): void {
  if (typeof window === 'undefined') return;
  const channel = getCrossTabChannel();
  if (channel) {
    channel.postMessage(message);
  } else {
    const key = `mark-ct-${Date.now()}`;
    try {
      localStorage.setItem(key, JSON.stringify(message));
      setTimeout(() => {
        try {
          localStorage.removeItem(key);
        } catch {}
      }, 500);
    } catch {}
  }
}

interface ChatPanelProps {
  embedded?: boolean;
}

const defaultControl = (): ControlState => ({
  kind: null,
  actionType: 'intent',
});

function isLegacyPrimaryIntentControl(control: ControlState): boolean {
  return (
    control.actionType === 'intent' &&
    control.kind === 'select' &&
    Array.isArray(control.options) &&
    control.options.length === primaryIntentActions.length &&
    control.options.every((option, index) => option === primaryIntentActions[index])
  );
}

export function ChatPanel({ embedded = false }: ChatPanelProps) {
  const { session, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const [chatHydrated, setChatHydrated] = useState(false);
  const [open, setOpen] = useState(embedded);
  const [messages, setMessages] = useState<ChatRecord[]>(
    typeof window !== 'undefined' && sessionStorage.getItem('hasGreeted') === 'true'
      ? []
      : [initialAssistantMessage(null)]
  );
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [flow, setFlow] = useState<FlowState | null>(null);
  const [control, setControl] = useState<ControlState>(defaultControl);
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);
  const [memoryCards, setMemoryCards] = useState<MemoryCard[]>([]);
  const [pendingCsat, setPendingCsat] = useState<PendingCsat | null>(null);
  const [submittingCsat, setSubmittingCsat] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const breakReminderTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const secondBreakReminderTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const complaintFinalizeRef = useRef(false);
  const loginGreetingHandledRef = useRef<string | null>(null);
  const breakReminderHandledRef = useRef<string | null>(null);
  const secondBreakReminderHandledRef = useRef<string | null>(null);
  const inferredLoginAtRef = useRef<{ email: string; value: number } | null>(null);
  const lastActivityAtRef = useRef<number>(Date.now());
  const lastCsatAtRef = useRef<number>(0);
  const lastAutoCheckinAtRef = useRef<number>(0);
  const lastAutoReminderRef = useRef<{ key: string; at: number } | null>(null);
  const threadInitRef = useRef<string | null>(null);
  const crossTabGreetedRef = useRef(false);
  const crossTabNudgesRef = useRef<Set<string>>(new Set());

  const markActivity = () => {
    lastActivityAtRef.current = Date.now();
  };

  const isStillActive = (nowMs: number) => {
    const recentlyActive = nowMs - lastActivityAtRef.current <= ACTIVE_WINDOW_MS;
    const pageVisible = typeof document === 'undefined' || document.visibilityState === 'visible';
    return recentlyActive && pageVisible;
  };

  const quickActions = useMemo(() => {
    if (flow) {
      return primaryIntentActions;
    }
    const lastUserMessage = [...messages].reverse().find((message) => message.role === 'user')?.text ?? '';
    return contextualQuickActions(lastUserMessage);
  }, [flow, messages]);

  const queueCsatPrompt = (meta?: { conversationId?: string; intent?: string; sentiment?: string }) => {
    const now = Date.now();
    if (now - lastCsatAtRef.current < CSAT_COOLDOWN_MS) {
      return;
    }

    setPendingCsat({
      conversationId: meta?.conversationId,
      intent: meta?.intent,
      sentiment: meta?.sentiment,
      askedAt: now,
    });
    lastCsatAtRef.current = now;
  };

  const submitCsat = async (rating: number) => {
    if (!pendingCsat || submittingCsat) {
      return;
    }

    setSubmittingCsat(true);
    try {
      const authToken = typeof window !== 'undefined' ? window.localStorage.getItem('auth_token') : null;
      await fetch('/api/chat/csat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rating,
          conversationId: pendingCsat.conversationId,
          intent: pendingCsat.intent,
          sentiment: pendingCsat.sentiment,
          userEmail: session?.email,
          userName: session?.name,
          ...(authToken ? { authToken } : {}),
        }),
      });

      const thanks =
        rating >= 4
          ? 'Thanks for the rating. I will keep this style of help going.'
          : 'Thanks for the honest rating. I will keep improving how I help you.';
      setMessages((current) => [...current, { id: shortId(), role: 'assistant', text: thanks }]);
      await persistChatMessage({ role: 'assistant', content: thanks, conversationId: pendingCsat.conversationId });
    } catch {
      // Ignore CSAT submission failures; core chat should continue uninterrupted.
    } finally {
      setSubmittingCsat(false);
      setPendingCsat(null);
    }
  };

  const tryInferredReminder = async (message: string): Promise<string | null> => {
    const inferred = inferReminderFromMessage(message);
    if (!inferred) {
      return null;
    }

    const dedupeKey = `${inferred.reminderType}|${inferred.title}|${inferred.scheduleKind}|${inferred.runAtIso ?? ''}`.toLowerCase();
    const now = Date.now();
    if (
      lastAutoReminderRef.current &&
      lastAutoReminderRef.current.key === dedupeKey &&
      now - lastAutoReminderRef.current.at < AUTO_REMINDER_DEDUPE_MS
    ) {
      return 'I already set that reminder just now. You are all set.';
    }

    try {
      await createWellbeingReminder({
        reminder_type: inferred.reminderType,
        title: inferred.title,
        message: inferred.message,
        schedule_kind: inferred.scheduleKind,
        run_at: inferred.runAtIso,
        timezone: 'UTC',
      });

      lastAutoReminderRef.current = { key: dedupeKey, at: now };
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('mark:reminders-updated'));
      }

      showToast({
        title: 'Reminder inferred',
        description: `${inferred.title} (${inferred.humanSchedule})`,
        variant: 'success',
      });

      return `Done. I set a ${inferred.reminderType} reminder for "${inferred.title}" (${inferred.humanSchedule}).`;
    } catch {
      showToast({
        title: 'Could not create reminder',
        description: 'I could not schedule it right now. Please try again in a moment.',
        variant: 'error',
      });
      return null;
    }
  };

  const tryInferredCheckin = async (message: string): Promise<string | null> => {
    const mood = inferDailyMood(message);
    if (!mood) {
      return null;
    }

    const now = Date.now();
    if (now - lastAutoCheckinAtRef.current < AUTO_CHECKIN_COOLDOWN_MS) {
      return null;
    }

    try {
      const response = await submitDailyCheckin({
        mood,
        message,
        wants_followup: hasStressSignal(message.toLowerCase()) || hasHrIssueSignal(message.toLowerCase()),
      });
      lastAutoCheckinAtRef.current = now;
      const triage = String(response.signal?.triage_level || 'none');

      showToast({
        title: 'Check-in inferred',
        description: `Captured from your message (${mood}, signal: ${triage}).`,
        variant: 'success',
      });

      return `I noted that as your check-in (${mood}). ${response.suggested_next_step}`;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    if (authLoading || !session?.email) {
      setMemoryCards([]);
      return;
    }

    let cancelled = false;
    const run = async () => {
      try {
        const authToken = typeof window !== 'undefined' ? window.localStorage.getItem('auth_token') : null;
        const response = await fetch('/api/chat/memory-cards', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            limit: 3,
            userEmail: session.email,
            userName: session.name,
            ...(authToken ? { authToken } : {}),
          }),
        });

        if (!response.ok) {
          if (!cancelled) setMemoryCards([]);
          return;
        }

        const data = (await response.json()) as {
          cards?: Array<{ title?: string; summary?: string; tags?: string[]; last_updated?: string }>;
        };

        if (cancelled) {
          return;
        }

        const cards: MemoryCard[] = (data.cards ?? [])
          .map((card) => ({
            title: String(card.title ?? 'Recent memory'),
            summary: String(card.summary ?? ''),
            tags: Array.isArray(card.tags) ? card.tags.map((tag) => String(tag)) : [],
            lastUpdated: String(card.last_updated ?? ''),
          }))
          .filter((card) => card.summary.trim().length > 0)
          .slice(0, 3);

        setMemoryCards(cards);
      } catch {
        if (!cancelled) {
          setMemoryCards([]);
        }
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [authLoading, session, session?.email, session?.name]);

  /** Load thread for the signed-in employee (isolated by email in localStorage). */
  useEffect(() => {
    if (authLoading) return;

    if (!session?.email) {
      setMessages([initialAssistantMessage(null)]);
      setFlow(null);
      setControl(defaultControl());
      setPendingCsat(null);
      setChatHydrated(true);
      return;
    }

    if (threadInitRef.current === session.email) {
      if (!chatHydrated) setChatHydrated(true);
      return;
    }
    threadInitRef.current = session.email;

    const snap = loadChatSnapshot(session.email);
    if (snap && snap.messages.length > 0) {
      setMessages(snap.messages);
      setFlow(snap.flow);
      setControl(isLegacyPrimaryIntentControl(snap.control) ? defaultControl() : snap.control);
    } else {
      const hasGreeted = typeof window !== 'undefined' && sessionStorage.getItem('hasGreeted') === 'true';
      if (!hasGreeted) {
        setMessages([initialAssistantMessage(session)]);
        sessionStorage.setItem('hasGreeted', 'true');
      } else {
        setMessages([]);
      }
      setFlow(null);
      setControl(defaultControl());
    }
    setPendingCsat(null);
    setChatHydrated(true);
  }, [authLoading, session, session?.email, session?.name]);

  /** Persist after each meaningful update (debounced). */
  useEffect(() => {
    if (!chatHydrated || !session?.email) return;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      saveChatSnapshot(session.email, { messages, flow, control });
    }, 350);

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [chatHydrated, session?.email, messages, flow, control]);

  useEffect(() => {
    if (open) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, open, typing]);

  useEffect(() => {
    if (embedded) {
      setOpen(true);
    }
  }, [embedded]);

  useEffect(() => {
    if (isLegacyPrimaryIntentControl(control)) {
      setControl(defaultControl());
    }
  }, [control]);

  useEffect(() => {
    lastActivityAtRef.current = Date.now();
  }, [session?.email]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const onActivity = () => {
      lastActivityAtRef.current = Date.now();
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        lastActivityAtRef.current = Date.now();
      }
    };

    window.addEventListener('pointerdown', onActivity);
    window.addEventListener('keydown', onActivity);
    window.addEventListener('focus', onActivity);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.removeEventListener('pointerdown', onActivity);
      window.removeEventListener('keydown', onActivity);
      window.removeEventListener('focus', onActivity);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleMessage = (message: CrossTabMessage) => {
      if (message.type === 'mark:greeted') {
        sessionStorage.setItem('hasGreeted', 'true');
        crossTabGreetedRef.current = true;
      } else if (message.type === 'mark:nudged' && message.nudgeType) {
        crossTabNudgesRef.current.add(message.nudgeType);
      }
    };

    const channel = getCrossTabChannel();
    if (channel) {
      const onMessage = (event: MessageEvent<CrossTabMessage>) => handleMessage(event.data);
      channel.addEventListener('message', onMessage);
      return () => channel.removeEventListener('message', onMessage);
    }

    const onStorage = (event: StorageEvent) => {
      if (!event.key?.startsWith('mark-ct-') || !event.newValue) return;
      try {
        const message = JSON.parse(event.newValue) as CrossTabMessage;
        handleMessage(message);
      } catch {}
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  useEffect(() => {
    if (authLoading || !chatHydrated || !session?.email) return;

    const hasGreeted = typeof window !== 'undefined' && sessionStorage.getItem('hasGreeted') === 'true';
    if (hasGreeted || crossTabGreetedRef.current) {
      return;
    }

    let loginAtMs = session.loginAtMs;
    if (!loginAtMs) {
      if (!inferredLoginAtRef.current || inferredLoginAtRef.current.email !== session.email) {
        inferredLoginAtRef.current = { email: session.email, value: Date.now() };
      }
      loginAtMs = inferredLoginAtRef.current.value;
    }

    const loginKey = `${session.email}:${loginAtMs}`;
    if (loginGreetingHandledRef.current === loginKey) {
      return;
    }

    const greeting = loginGreetingText(session);
    const alreadyShownForLogin = (session.loginGreetingShownAtMs ?? 0) >= loginAtMs;

    if (!alreadyShownForLogin) {
      setMessages((current) => {
        if (crossTabGreetedRef.current) {
          return current;
        }
        const lastMessage = current[current.length - 1];
        if (lastMessage?.role === 'assistant' && lastMessage.text === greeting) {
          return current;
        }
        return [...current, { id: shortId(), role: 'assistant', text: greeting }];
      });

      patchSession({
        loginAtMs,
        breakReminderAtMs: session.breakReminderAtMs ?? loginAtMs + FIRST_BREAK_REMINDER_DELAY_MS,
        secondBreakReminderAtMs: session.secondBreakReminderAtMs ?? loginAtMs + SECOND_BREAK_REMINDER_FALLBACK_DELAY_MS,
        loginGreetingShownAtMs: Date.now(),
      });
    }

    sessionStorage.setItem('hasGreeted', 'true');
    loginGreetingHandledRef.current = loginKey;
    broadcastCrossTab({ type: 'mark:greeted' });
  }, [
    authLoading,
    chatHydrated,
    session,
    session?.email,
    session?.loginAtMs,
    session?.loginGreetingShownAtMs,
    session?.breakReminderAtMs,
    session?.secondBreakReminderAtMs,
    session?.name,
  ]);

  useEffect(() => {
    if (breakReminderTimerRef.current) {
      clearTimeout(breakReminderTimerRef.current);
      breakReminderTimerRef.current = null;
    }

    if (authLoading || !chatHydrated || !session?.email || session.role !== 'employee') {
      return;
    }

    let loginAtMs = session.loginAtMs;
    if (!loginAtMs) {
      if (!inferredLoginAtRef.current || inferredLoginAtRef.current.email !== session.email) {
        inferredLoginAtRef.current = { email: session.email, value: Date.now() };
      }
      loginAtMs = inferredLoginAtRef.current.value;
    }

    const reminderAtMs = session.breakReminderAtMs ?? loginAtMs + FIRST_BREAK_REMINDER_DELAY_MS;
    if (!session.loginAtMs || !session.breakReminderAtMs || !session.secondBreakReminderAtMs) {
      patchSession({
        loginAtMs,
        breakReminderAtMs: reminderAtMs,
        secondBreakReminderAtMs: session.secondBreakReminderAtMs ?? loginAtMs + SECOND_BREAK_REMINDER_FALLBACK_DELAY_MS,
      });
    }

    const loginKey = `${session.email}:${loginAtMs}`;
    const alreadyShownForLogin = (session.breakReminderShownAtMs ?? 0) >= loginAtMs;

    if (alreadyShownForLogin || breakReminderHandledRef.current === loginKey) {
      return;
    }

    const showBreakReminder = () => {
      if (breakReminderHandledRef.current === loginKey) {
        return;
      }
      if (crossTabNudgesRef.current.has('break')) {
        breakReminderHandledRef.current = loginKey;
        return;
      }

      breakReminderHandledRef.current = loginKey;
      const reminder = breakReminderText(session, loginAtMs, Date.now());
      setMessages((current) => [...current, { id: shortId(), role: 'assistant', text: reminder }]);

      patchSession({
        loginAtMs,
        breakReminderAtMs: reminderAtMs,
        breakReminderShownAtMs: Date.now(),
      });
      broadcastCrossTab({ type: 'mark:nudged', nudgeType: 'break' });
    };

    const delayMs = reminderAtMs - Date.now();
    if (delayMs <= 0) {
      showBreakReminder();
      return;
    }

    breakReminderTimerRef.current = setTimeout(showBreakReminder, delayMs);

    return () => {
      if (breakReminderTimerRef.current) {
        clearTimeout(breakReminderTimerRef.current);
        breakReminderTimerRef.current = null;
      }
    };
  }, [
    authLoading,
    chatHydrated,
    session,
    session?.email,
    session?.role,
    session?.name,
    session?.loginAtMs,
    session?.breakReminderAtMs,
    session?.breakReminderShownAtMs,
  ]);

  useEffect(() => {
    if (secondBreakReminderTimerRef.current) {
      clearTimeout(secondBreakReminderTimerRef.current);
      secondBreakReminderTimerRef.current = null;
    }

    if (authLoading || !chatHydrated || !session?.email || session.role !== 'employee') {
      return;
    }

    let loginAtMs = session.loginAtMs;
    if (!loginAtMs) {
      if (!inferredLoginAtRef.current || inferredLoginAtRef.current.email !== session.email) {
        inferredLoginAtRef.current = { email: session.email, value: Date.now() };
      }
      loginAtMs = inferredLoginAtRef.current.value;
    }

    const secondReminderAtMs = session.secondBreakReminderAtMs ?? loginAtMs + SECOND_BREAK_REMINDER_FALLBACK_DELAY_MS;
    if (!session.loginAtMs || !session.secondBreakReminderAtMs) {
      patchSession({ loginAtMs, secondBreakReminderAtMs: secondReminderAtMs });
    }

    const loginKey = `${session.email}:${loginAtMs}`;
    const alreadyShownForLogin = (session.secondBreakReminderShownAtMs ?? 0) >= loginAtMs;

    if (alreadyShownForLogin || secondBreakReminderHandledRef.current === loginKey) {
      return;
    }

    const scheduleRetry = (nowMs: number) => {
      const retryUntilMs = secondReminderAtMs + 60 * 60 * 1000;
      if (nowMs >= retryUntilMs) {
        return;
      }
      secondBreakReminderTimerRef.current = setTimeout(showSecondBreakReminder, 15 * 60 * 1000);
    };

    const showSecondBreakReminder = () => {
      if (secondBreakReminderHandledRef.current === loginKey) {
        return;
      }
      if (crossTabNudgesRef.current.has('second-break')) {
        secondBreakReminderHandledRef.current = loginKey;
        return;
      }

      const nowMs = Date.now();
      if (!isStillActive(nowMs)) {
        scheduleRetry(nowMs);
        return;
      }

      secondBreakReminderHandledRef.current = loginKey;
      const reminder = secondBreakReminderText(session, loginAtMs, nowMs);
      setMessages((current) => [...current, { id: shortId(), role: 'assistant', text: reminder }]);

      patchSession({
        loginAtMs,
        secondBreakReminderAtMs: secondReminderAtMs,
        secondBreakReminderShownAtMs: nowMs,
      });
      broadcastCrossTab({ type: 'mark:nudged', nudgeType: 'second-break' });
    };

    const delayMs = secondReminderAtMs - Date.now();
    if (delayMs <= 0) {
      showSecondBreakReminder();
      return;
    }

    secondBreakReminderTimerRef.current = setTimeout(showSecondBreakReminder, delayMs);

    return () => {
      if (secondBreakReminderTimerRef.current) {
        clearTimeout(secondBreakReminderTimerRef.current);
        secondBreakReminderTimerRef.current = null;
      }
    };
  }, [
    authLoading,
    chatHydrated,
    session,
    session?.email,
    session?.role,
    session?.name,
    session?.loginAtMs,
    session?.secondBreakReminderAtMs,
    session?.secondBreakReminderShownAtMs,
  ]);

  const controlLabel = useMemo(() => {
    if (control.kind === 'date') return control.label ?? 'Pick a date';
    if (control.kind === 'select') return control.label ?? 'Choose one option';
    if (control.kind === 'choice') return control.label ?? 'Choose yes or no';
    return null;
  }, [control]);

  const appendAssistant = async (text: string, nextFlow?: Partial<FlowState>, nextControl?: ControlState) => {
    const assistantMessage: ChatRecord = { id: shortId(), role: 'assistant', text };
    setMessages((current) => [...current, assistantMessage]);
    setControl(nextControl ?? { kind: null });
    setFlow((current) => (current ? { ...current, ...nextFlow } : nextFlow ? ({ intent: 'general', step: 'start', ...nextFlow } as FlowState) : current));
    setTyping(false);
    const conversationId = nextFlow?.conversationId ?? flow?.conversationId;
    await persistChatMessage({ role: 'assistant', content: text, conversationId });
    queueCsatPrompt({
      conversationId,
      intent: nextFlow?.intent ?? flow?.intent,
    });
  };

  const finalizeFlow = async (summary: string) => {
    await appendAssistant(summary, { intent: 'general', step: 'done' }, { kind: null });
    setFlow(null);
    setControl(defaultControl());
  };

  const startFlow = async (intent: Intent, seedMessage?: string) => {
    if (intent === 'complaint') {
      const seededIssue = (seedMessage ?? '').trim();
      if (seededIssue && complaintDetailIsSufficient(seededIssue, seededIssue)) {
        const nextFlow: FlowState = { intent, step: 'department', issue: seededIssue };
        setFlow(nextFlow);
        await appendAssistant(
          'Got you. I can raise this with HR now. Which team should I route it to?',
          nextFlow,
          { kind: 'select', label: 'Department', options: departmentOptions, actionType: 'value' }
        );
        return;
      }

      const nextFlow: FlowState = { intent, step: 'issue', issue: seededIssue || undefined };
      setFlow(nextFlow);
      setControl({ kind: null, actionType: 'value' });
      await appendAssistant(
        seededIssue
          ? 'Thanks. Share a bit more context (who was involved and roughly when), then I will raise it.'
          : 'Ah, that sounds rough. What happened?',
        nextFlow
      );
      return;
    }

    if (intent === 'leave') {
      setFlow({ intent, step: 'startDate' });
      await appendAssistant('Sure thing. What start date should I use?', { intent, step: 'startDate' }, { kind: 'date', label: 'Start date', actionType: 'value' });
      return;
    }

    if (intent === 'policy') {
      setFlow({ intent, step: 'policyTopic' });
      await appendAssistant('Got it. Which policy should I pull up?', { intent, step: 'policyTopic' }, { kind: 'select', label: 'Policy topic', options: policyOptions, actionType: 'value' });
      return;
    }

    await finalizeFlow('Yep, I can help with that. Want me to turn it into a ticket, or keep helping here?');
  };

  const handleQuickAction = async (value: string, options?: { echoUser?: boolean }) => {
    markActivity();
    const echoUser = options?.echoUser ?? true;
    if (control.actionType === 'intent') {
      const intent = intentFromAction(value);
      if (echoUser) {
        setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
        await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      }
      setTyping(true);
      await startFlow(intent);
      setTyping(false);
      return;
    }

    if (!flow) return;

    const currentFlow = flow;

    if (currentFlow.intent === 'complaint' && currentFlow.step === 'department') {
      if (echoUser) {
        setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      }
      setFlow({ ...currentFlow, department: value, step: 'anonymous' });
      if (echoUser) {
        await persistChatMessage({ role: 'user', content: value, conversationId: currentFlow.conversationId });
      }
      await appendAssistant('Do you want this to stay anonymous?', { ...currentFlow, department: value, step: 'anonymous' }, { kind: 'choice', label: 'Anonymous?', options: ['Yes', 'No'], actionType: 'value' });
      return;
    }

    if (currentFlow.intent === 'leave' && currentFlow.step === 'leaveType') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: currentFlow.conversationId });

      const leaveSummary = `Leave request: ${value} from ${humanDate(currentFlow.startDate ?? '')} to ${humanDate(currentFlow.endDate ?? '')}.`;
      const leaveTicketId = await createTicketFromChat(
        {
          category: 'leave',
          query: leaveSummary,
          priority: 'medium',
        },
        session
      );

      await finalizeFlow(
        leaveTicketId
          ? `Done. I raised your leave request ticket (${leaveTicketId}) for ${humanDate(currentFlow.startDate ?? '')} to ${humanDate(currentFlow.endDate ?? '')}.`
          : `Got it. I queued your ${value.toLowerCase()} request from ${humanDate(currentFlow.startDate ?? '')} to ${humanDate(currentFlow.endDate ?? '')}.`
      );
      setFlow(null);
      setControl({ kind: null });
      return;
    }

    if (currentFlow.intent === 'policy' && currentFlow.step === 'policyTopic') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: currentFlow.conversationId });
      setTyping(true);
      const reply = await fetchPolicyRagAnswer(value, session);
      setTyping(false);
      await finalizeFlow(reply);
      return;
    }
  };

  const handlePrimaryIntent = async (value: string) => {
    markActivity();
    if (value === 'Take 5-minute reset') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await appendAssistant(
        "Absolutely. Try this quick reset: inhale for 4 seconds, exhale for 6 seconds, repeat 5 times. I'm here when you're ready."
      );
      setTyping(false);
      return;
    }

    if (value === 'Raise confidential ticket') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await startFlow('complaint', 'I want to raise a confidential issue');
      setTyping(false);
      return;
    }

    if (value === 'Talk through it') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await appendAssistant('I am with you. Tell me the one thing that feels heaviest right now, and we will take it step by step.');
      setTyping(false);
      return;
    }

    if (value === 'Leave policy') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      const reply = await fetchPolicyRagAnswer('Leave policy', session);
      setTyping(false);
      await appendAssistant(reply);
      return;
    }

    if (value === 'Draft manager note') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await appendAssistant('Sure. You can send this: "Hi [Manager], I am not feeling well today and would like to request leave on [date]. I will ensure handover for urgent tasks."');
      setTyping(false);
      return;
    }

    if (value === 'Talk to HR') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await startFlow('complaint', 'I need to speak to HR');
      setTyping(false);
      return;
    }

    const intent = intentFromAction(value);
    setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
    await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
    setTyping(true);
    await startFlow(intent);
    setTyping(false);
  };

  const handleDateSubmit = async (value: string) => {
    markActivity();
    if (!flow) return;

    setMessages((current) => [...current, { id: shortId(), role: 'user', text: humanDate(value) }]);
    await persistChatMessage({ role: 'user', content: value, conversationId: flow.conversationId });

    if (flow.intent === 'leave' && flow.step === 'startDate') {
      setFlow({ ...flow, startDate: value, step: 'endDate' });
      await appendAssistant('What end date works?', { ...flow, startDate: value, step: 'endDate' }, { kind: 'date', label: 'End date' });
      return;
    }

    if (flow.intent === 'leave' && flow.step === 'endDate') {
      setFlow({ ...flow, endDate: value, step: 'leaveType' });
      await appendAssistant('Which leave type is this?', { ...flow, endDate: value, step: 'leaveType' }, { kind: 'select', label: 'Leave type', options: leaveTypeOptions, actionType: 'value' });
      return;
    }

    setControl({ kind: null });
  };

  const handleChoice = async (value: 'Yes' | 'No', options?: { echoUser?: boolean }) => {
    markActivity();
    if (!flow || flow.intent !== 'complaint' || flow.step !== 'anonymous') return;
    if (complaintFinalizeRef.current) return;
    complaintFinalizeRef.current = true;
    try {
      const currentFlow = { ...flow, anonymous: value === 'Yes', step: 'done' as const };
      setFlow(currentFlow);
      setControl({ kind: null });
      const echoUser = options?.echoUser ?? true;
      if (echoUser) {
        setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
        await persistChatMessage({ role: 'user', content: value, conversationId: flow.conversationId });
      }

      const complaintSummary = [
        `Issue: ${currentFlow.issue ?? 'Not specified'}`,
        `Department: ${currentFlow.department ?? 'People Ops'}`,
        `Anonymous: ${value}`,
      ].join(' | ');

      const complaintTicketId = await createTicketFromChat(
        {
          category: 'complaint',
          query: complaintSummary,
          priority: 'high',
        },
        session
      );

      await finalizeFlow(
        complaintTicketId
          ? value === 'Yes'
            ? `Got it. I created an anonymous complaint ticket (${complaintTicketId}) and notified HR.`
            : `Done. I created complaint ticket (${complaintTicketId}) and shared it with HR for review.`
          : value === 'Yes'
            ? 'Got it. I created an anonymous complaint ticket and kept HR in the loop.'
            : 'Done. I created the ticket and shared it with HR for review.'
      );
    } finally {
      complaintFinalizeRef.current = false;
    }
  };

  const handleSubmit = async () => {
    markActivity();
    const trimmed = input.trim();
    if (!trimmed) return;

    setInput('');
    setSelectedFile(null);
    setMessages((current) => [...current, { id: shortId(), role: 'user', text: trimmed }]);
    await persistChatMessage({ role: 'user', content: trimmed, conversationId: flow?.conversationId });
    setTyping(true);

    // Intent lock: guided workflows must stay deterministic until completion.
    // Structured wizards (leave / complaint / policy) must not call the LLM.
    const isStructuredGuidedFlow =
      flow !== null &&
      (flow.intent === 'leave' || flow.intent === 'complaint' || flow.intent === 'policy');

    if (!flow) {
      const reminderReply = await tryInferredReminder(trimmed);
      if (reminderReply) {
        await appendAssistant(reminderReply);
        return;
      }

      const checkinReply = await tryInferredCheckin(trimmed);
      if (checkinReply) {
        await appendAssistant(checkinReply);
        return;
      }

      if (isLeaveBalanceQuestion(trimmed)) {
        await finalizeFlow(
          "I can help with leave balance. I don't have direct leave-ledger access in this chat yet, so please check the leave portal or HR for the exact number. If you want, I can still file a leave request for you right now."
        );
        setTyping(false);
        return;
      }
      const intent = inferIntent(trimmed);
      if (intent !== 'general') {
        await startFlow(intent, trimmed);
        setTyping(false);
        return;
      }
    }

    if (!isStructuredGuidedFlow && !flow) {
      const bridgeState: Partial<FlowState> = flow ?? { intent: 'general', step: 'start' };
      const backendReply = await askBackend(trimmed, bridgeState, session, selectedFile);
      if (backendReply?.reply) {
        setTyping(false);
        setMessages((current) => [...current, { id: shortId(), role: 'assistant', text: backendReply.reply ?? '' }]);
        if (backendReply.state) {
          setFlow((current) => ({ ...(current ?? { intent: 'general', step: 'start' }), ...backendReply.state } as FlowState));
        }
        setControl({ kind: null });
        setSelectedFile(null);
        const bridgeConv = (backendReply.state as { conversationId?: string } | undefined)?.conversationId;
        await persistChatMessage({
          role: 'assistant',
          content: backendReply.reply ?? '',
          conversationId: bridgeConv ?? undefined,
        });
        queueCsatPrompt({
          conversationId: bridgeConv ?? undefined,
          intent: (backendReply.state as { intent?: string } | undefined)?.intent,
          sentiment: (backendReply.state as { sentiment?: string } | undefined)?.sentiment,
        });
        return;
      }

      // Reliability fallback: still answer locally when backend is unavailable.
      await appendAssistant(assistantReplyForGeneral(trimmed));
      return;
    }

    if (!flow) {
      setTyping(false);
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'issue') {
      const nextIssue = flow.issue ? `${flow.issue}\n\n${trimmed}` : trimmed;
      if (!complaintDetailIsSufficient(nextIssue, trimmed)) {
        setFlow({ ...flow, issue: nextIssue, step: 'issue' });
        await appendAssistant(
          "Thanks - add a little more (what happened, who was involved, roughly when). When you're ready, say 'raise a ticket' or keep typing.",
          { ...flow, issue: nextIssue, step: 'issue' },
          { kind: null, actionType: 'value' }
        );
        return;
      }
      setFlow({ ...flow, issue: nextIssue, step: 'department' });
      await appendAssistant(
        'Which team should I route this to?',
        { ...flow, issue: nextIssue, step: 'department' },
        { kind: 'select', label: 'Department', options: departmentOptions, actionType: 'value' }
      );
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'department') {
      const match = detectDepartment(trimmed);
      if (match) {
        setTyping(false);
        await handleQuickAction(match, { echoUser: false });
        return;
      }
      await appendAssistant(
        `Tap a team button above, or type one of: ${departmentOptions.join(', ')}.`,
        flow,
        { kind: 'select', label: 'Department', options: departmentOptions, actionType: 'value' }
      );
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'anonymous') {
      const v = trimmed.toLowerCase();
      if (v === 'yes' || v === 'y' || v === 'no' || v === 'n') {
        setTyping(false);
        // handleSubmit already echoed the user's text; avoid duplicating it.
        // We still progress deterministically to ticket creation.
        const choice = v === 'yes' || v === 'y' ? 'Yes' : 'No';
        // Inline echo suppression by temporarily calling a non-echo path.
        const prevFlow = flow;
        setFlow({ ...prevFlow, anonymous: choice === 'Yes', step: 'done' });
        setControl({ kind: null });
        const complaintSummary = [
          `Issue: ${prevFlow.issue ?? 'Not specified'}`,
          `Department: ${prevFlow.department ?? 'People Ops'}`,
          `Anonymous: ${choice}`,
        ].join(' | ');
        const complaintTicketId = await createTicketFromChat(
          { category: 'complaint', query: complaintSummary, priority: 'high' },
          session
        );
        await finalizeFlow(
          complaintTicketId
            ? choice === 'Yes'
              ? `Got it. I created an anonymous complaint ticket (${complaintTicketId}) and notified HR.`
              : `Done. I created complaint ticket (${complaintTicketId}) and shared it with HR for review.`
            : choice === 'Yes'
              ? 'Got it. I created an anonymous complaint ticket and kept HR in the loop.'
              : 'Done. I created the ticket and shared it with HR for review.'
        );
        return;
      }
      await appendAssistant(
        'Reply yes or no (or use the buttons): should this stay anonymous?',
        flow,
        {
        kind: 'choice',
        label: 'Anonymous?',
        options: ['Yes', 'No'],
        actionType: 'value',
      });
      return;
    }

    if (flow.intent === 'policy') {
      await finalizeFlow(assistantReplyForGeneral(trimmed));
      return;
    }

    if (flow.intent === 'general') {
      await finalizeFlow(assistantReplyForGeneral(trimmed));
      return;
    }

    setTyping(false);
  };

  const controlArea = (
    <div className="border-t border-slate-200 bg-slate-50 px-4 py-3">
      {controlLabel ? <p className="mb-3 text-sm font-medium text-slate-600">{controlLabel}</p> : null}

      {control.kind === 'date' ? (
        <div className="flex items-center gap-3">
          <label className="flex flex-1 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
            <Calendar className="h-4 w-4 text-slate-400" />
            <input
              type="date"
              className="w-full bg-transparent text-slate-700 outline-none"
              onChange={(event) => {
                if (event.target.value) {
                  void handleDateSubmit(event.target.value);
                }
              }}
            />
          </label>
        </div>
      ) : null}

      {control.kind === 'select' ? (
        <div className="flex flex-wrap gap-2">
          {control.options?.map((option) => (
            <Button key={option} type="button" variant="outline" className="rounded-full bg-white px-4" onClick={() => void handleQuickAction(option)}>
              {option}
            </Button>
          ))}
        </div>
      ) : null}

      {control.kind === 'choice' ? (
        <div className="flex gap-3">
          <Button type="button" className="rounded-full px-5" onClick={() => void handleChoice('Yes')}>
            Yes
          </Button>
          <Button type="button" variant="outline" className="rounded-full px-5" onClick={() => void handleChoice('No')}>
            No
          </Button>
        </div>
      ) : null}
    </div>
  );

  const chatContent = (
    <>
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">Mark</p>
          <h2 className="text-lg font-semibold text-slate-900">{session?.role === 'hr' ? 'HR assistant channel' : 'Employee assistant'}</h2>
        </div>
        {!embedded ? (
          <button type="button" aria-label="Close Mark assistant" onClick={() => setOpen(false)} className="rounded-full p-2 text-slate-500 transition hover:bg-slate-200 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        ) : null}
      </div>

      <div className={cn('flex-1 space-y-4 overflow-y-auto bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] p-5')}>
        {authLoading || !chatHydrated ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
            <p>Loading your conversation…</p>
            <p className="max-w-xs text-xs text-slate-400">Threads are saved per signed-in employee.</p>
          </div>
        ) : (
          <>
            {memoryCards.length > 0 ? (
              <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-700">Your memory cards</p>
                <div className="mt-2 space-y-2">
                  {memoryCards.map((card, index) => (
                    <div key={`${card.title}-${index}`} className="rounded-xl border border-blue-100 bg-white/80 px-3 py-2">
                      <p className="text-xs font-semibold text-slate-900">{card.title}</p>
                      <p className="mt-1 text-xs leading-5 text-slate-600">{card.summary}</p>
                      {card.tags.length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {card.tags.slice(0, 3).map((tag) => (
                            <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                              {tag.replace(/_/g, ' ')}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((message) => (
              <ChatMessage key={message.id} role={message.role} text={message.text} timestamp={message.role === 'assistant' ? 'Mark' : 'You'} />
            ))}

            {typing ? (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-tl-sm bg-blue-50 px-4 py-3 text-sm text-slate-500 shadow-sm">Mark is typing...</div>
              </div>
            ) : null}

            <div ref={endRef} />
          </>
        )}
      </div>

      {authLoading || !chatHydrated ? null : (
        <div className="border-t border-slate-200 bg-white px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Quick actions for you</p>
          <div className="flex flex-wrap gap-1.5">
            {quickActions.map((option) => (
              <Button
                key={option}
                type="button"
                variant="outline"
                size="sm"
                className="h-7 rounded-full bg-white px-3 text-xs"
                onClick={() => void handlePrimaryIntent(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
      )}

      {!ENABLE_CSAT_PROMPT || authLoading || !chatHydrated || !pendingCsat ? null : (
        <div className="border-t border-slate-200 bg-slate-50 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Response quality</p>
          <p className="text-xs text-slate-600">How helpful was my last response?</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {[1, 2, 3, 4, 5].map((score) => (
              <Button
                key={score}
                type="button"
                variant="outline"
                size="sm"
                className="h-7 rounded-full bg-white px-3 text-xs"
                disabled={submittingCsat}
                onClick={() => void submitCsat(score)}
              >
                {score}
              </Button>
            ))}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 rounded-full px-3 text-xs"
              disabled={submittingCsat}
              onClick={() => setPendingCsat(null)}
            >
              Skip
            </Button>
          </div>
        </div>
      )}

      {authLoading || !chatHydrated ? null : control.kind !== null ? controlArea : null}
      {authLoading || !chatHydrated ? null : (
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => void handleSubmit()}
          disabled={typing}
          selectedFile={selectedFile}
          onFileChange={setSelectedFile}
        />
      )}
    </>
  );

  if (embedded) {
    return <div className="flex h-full flex-col">{chatContent}</div>;
  }

  return (
    <>
      <motion.button
        onClick={() => setOpen(true)}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.98 }}
        aria-label="Open Mark assistant"
        className={cn('fixed bottom-5 right-5 z-40 flex h-[60px] w-[60px] items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-600/25', open && 'hidden')}
      >
        <MessageSquare className="h-6 w-6" />
      </motion.button>

      <AnimatePresence>
        {open ? (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/5"
              onClick={() => setOpen(false)}
            />
            <div className="fixed bottom-[90px] right-4 z-50 flex h-[620px] max-h-[82vh] w-[460px] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-2xl">
              {chatContent}
            </div>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}