"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Calendar, MessageSquare, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatInput } from '@/components/ChatInput';
import { ChatMessage } from '@/components/ChatMessage';
import { persistChatMessage } from '@/lib/hr-data';
import { readSession } from '@/lib/session';
import { cn } from '@/lib/utils';

type Intent = 'general' | 'leave' | 'complaint' | 'policy';
type Step = 'start' | 'issue' | 'department' | 'anonymous' | 'startDate' | 'endDate' | 'leaveType' | 'policyTopic' | 'done';

interface FlowState {
  intent: Intent;
  step: Step;
  conversationId?: string;
  issue?: string;
  department?: string;
  anonymous?: boolean;
  startDate?: string;
  endDate?: string;
  leaveType?: string;
  policyTopic?: string;
}

interface ChatRecord {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

interface ControlState {
  kind: 'date' | 'select' | 'choice' | null;
  label?: string;
  options?: string[];
  actionType?: 'intent' | 'value';
}

const departmentOptions = ['Engineering', 'Sales', 'Marketing', 'People Ops', 'Finance', 'IT'];
const leaveTypeOptions = ['Paid leave', 'Sick leave', 'Work from home'];
const policyOptions = ['Leave policy', 'Payroll', 'Benefits', 'Remote work'];
const primaryIntentActions = ['Apply leave', 'Raise complaint', 'Ask policy'];

function initialAssistantMessage(): ChatRecord {
  return {
    id: 'welcome',
    role: 'assistant',
    text: 'Hi, I am Mark. Tell me what is going on and I will handle it step by step.',
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
  if (t.length >= 52) {
    return true;
  }
  if (t.length < 18) {
    return false;
  }
  return /\b(manager|supervisor|lead|credit|workplace|harass|bully|payroll|policy|leave|team|project|present|ignored|backfoot|complaint|hr\b|unfair|discriminat)/i.test(
    t
  );
}

function inferIntent(message: string): Intent {
  const value = message.toLowerCase();

  if (value.includes('leave') || value.includes('vacation') || value.includes('pto') || value.includes('time off')) {
    return 'leave';
  }

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

  if (value.includes('policy') || value.includes('handbook') || value.includes('benefit') || value.includes('how do')) {
    return 'policy';
  }

  return 'general';
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
  if (value.includes('complaint')) return 'complaint';
  if (value.includes('policy')) return 'policy';
  return 'general';
}

async function askBackend(
  message: string,
  state: Partial<FlowState>,
  session: ReturnType<typeof readSession>
) {
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        state,
        userEmail: session?.email,
        userName: session?.name,
        userRole: session?.role,
      }),
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as { reply?: string; state?: Partial<FlowState> };
  } catch {
    return null;
  }
}

function assistantReplyForGeneral(message: string): string {
  const value = message.toLowerCase();

  if (value.includes('policy')) {
    return 'I can help with policy questions. Which policy should I check?';
  }

  if (value.includes('benefit')) {
    return 'I can pull up benefits details. Want me to explain medical, leave, or retirement?';
  }

  return 'I hear you. Want me to raise this as a ticket or keep guiding you here?';
}

async function createTicketFromChat(
  input: {
    category: 'leave' | 'complaint' | 'policy' | 'general';
    query: string;
    priority?: 'low' | 'medium' | 'high' | 'critical';
  },
  session: ReturnType<typeof readSession>
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

interface ChatPanelProps {
  embedded?: boolean;
}

export function ChatPanel({ embedded = false }: ChatPanelProps) {
  const session = readSession();
  const [open, setOpen] = useState(embedded);
  const [messages, setMessages] = useState<ChatRecord[]>([initialAssistantMessage()]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [flow, setFlow] = useState<FlowState | null>(null);
  const [control, setControl] = useState<ControlState>({
    kind: 'select',
    label: 'Choose what you need',
    options: primaryIntentActions,
    actionType: 'intent',
  });
  const endRef = useRef<HTMLDivElement | null>(null);

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
    await persistChatMessage({ role: 'assistant', content: text, conversationId: nextFlow?.conversationId ?? flow?.conversationId });
  };

  const finalizeFlow = async (summary: string) => {
    await appendAssistant(summary, { intent: 'general', step: 'done' }, { kind: null });
    setFlow(null);
  };

  const startFlow = async (intent: Intent) => {
    if (intent === 'complaint') {
      setFlow({ intent, step: 'issue' });
      setControl({ kind: null, actionType: 'value' });
      await appendAssistant('That sounds frustrating. What happened?', { intent, step: 'issue' });
      return;
    }

    if (intent === 'leave') {
      setFlow({ intent, step: 'startDate' });
      await appendAssistant('Of course. What start date should I use?', { intent, step: 'startDate' }, { kind: 'date', label: 'Start date', actionType: 'value' });
      return;
    }

    if (intent === 'policy') {
      setFlow({ intent, step: 'policyTopic' });
      await appendAssistant('Which policy should I pull up?', { intent, step: 'policyTopic' }, { kind: 'select', label: 'Policy topic', options: policyOptions, actionType: 'value' });
      return;
    }

    await finalizeFlow('I can help with that. Want me to turn it into a ticket or keep answering here?');
  };

  const handleQuickAction = async (value: string) => {
    if (control.actionType === 'intent') {
      const intent = intentFromAction(value);
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: flow?.conversationId });
      setTyping(true);
      await startFlow(intent);
      setTyping(false);
      return;
    }

    if (!flow) return;

    const currentFlow = flow;

    if (currentFlow.intent === 'complaint' && currentFlow.step === 'department') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      setFlow({ ...currentFlow, department: value, step: 'anonymous' });
      await persistChatMessage({ role: 'user', content: value, conversationId: currentFlow.conversationId });
      await appendAssistant('Should I keep this anonymous?', { ...currentFlow, department: value, step: 'anonymous' }, { kind: 'choice', label: 'Anonymous?', options: ['Yes', 'No'], actionType: 'value' });
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
          ? `Done. I have created your leave request ticket (${leaveTicketId}) for ${humanDate(currentFlow.startDate ?? '')} to ${humanDate(currentFlow.endDate ?? '')}.`
          : `Got it. I have queued your ${value.toLowerCase()} request from ${humanDate(currentFlow.startDate ?? '')} to ${humanDate(currentFlow.endDate ?? '')}.`
      );
      setFlow(null);
      setControl({ kind: null });
      return;
    }

    if (currentFlow.intent === 'policy' && currentFlow.step === 'policyTopic') {
      setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
      await persistChatMessage({ role: 'user', content: value, conversationId: currentFlow.conversationId });
      await finalizeFlow(`I can help with ${value.toLowerCase()}. If you want, I can turn this into a follow-up for HR.`);
      return;
    }
  };

  const handleDateSubmit = async (value: string) => {
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

  const handleChoice = async (value: 'Yes' | 'No') => {
    if (!flow || flow.intent !== 'complaint' || flow.step !== 'anonymous') return;

    setMessages((current) => [...current, { id: shortId(), role: 'user', text: value }]);
    await persistChatMessage({ role: 'user', content: value, conversationId: flow.conversationId });

    const complaintSummary = [
      `Issue: ${flow.issue ?? 'Not specified'}`,
      `Department: ${flow.department ?? 'People Ops'}`,
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
          ? `Understood. I created an anonymous complaint ticket (${complaintTicketId}) and notified HR.`
          : `Thanks. I created complaint ticket (${complaintTicketId}) and shared it with HR for review.`
        : value === 'Yes'
          ? 'Understood. I have created an anonymous complaint ticket and will keep HR looped in.'
          : 'Thanks. I have created the ticket and shared it with HR for review.'
    );
  };

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    setInput('');
    setMessages((current) => [...current, { id: shortId(), role: 'user', text: trimmed }]);
    await persistChatMessage({ role: 'user', content: trimmed, conversationId: flow?.conversationId });
    setTyping(true);

    // Guided flows (leave / complaint / policy) must not call the LLM — it was hijacking the ticket path.
    const inGuidedFlow = flow !== null;
    if (!inGuidedFlow) {
      const backendReply = await askBackend(trimmed, { intent: 'general', step: 'start' }, session);
      if (backendReply?.reply) {
        setTyping(false);
        setMessages((current) => [...current, { id: shortId(), role: 'assistant', text: backendReply.reply ?? '' }]);
        if (backendReply.state) {
          setFlow((current) => ({ ...(current ?? { intent: 'general', step: 'start' }), ...backendReply.state } as FlowState));
        }
        setControl({ kind: null });
        const bridgeConv = (backendReply.state as { conversationId?: string } | undefined)?.conversationId;
        await persistChatMessage({
          role: 'assistant',
          content: backendReply.reply ?? '',
          conversationId: bridgeConv ?? undefined,
        });
        return;
      }
    }

    if (!flow) {
      await startFlow(inferIntent(trimmed));
      setTyping(false);
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'issue') {
      const nextIssue = flow.issue ? `${flow.issue}\n\n${trimmed}` : trimmed;
      if (!complaintDetailIsSufficient(nextIssue, trimmed)) {
        setFlow({ ...flow, issue: nextIssue, step: 'issue' });
        await appendAssistant(
          'Thanks — add a bit more (what happened, who was involved, roughly when). When you’re ready, say “raise a ticket” or keep typing.',
          { ...flow, issue: nextIssue, step: 'issue' },
          { kind: null, actionType: 'value' }
        );
        return;
      }
      setFlow({ ...flow, issue: nextIssue, step: 'department' });
      await appendAssistant(
        'Which department should I route this to?',
        { ...flow, issue: nextIssue, step: 'department' },
        { kind: 'select', label: 'Department', options: departmentOptions, actionType: 'value' }
      );
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'department') {
      const match = departmentOptions.find((d) => d.toLowerCase() === trimmed.toLowerCase());
      if (match) {
        setTyping(false);
        await handleQuickAction(match);
        return;
      }
      await appendAssistant(
        `Tap a department button above, or type one of: ${departmentOptions.join(', ')}.`,
        flow,
        { kind: 'select', label: 'Department', options: departmentOptions, actionType: 'value' }
      );
      return;
    }

    if (flow.intent === 'complaint' && flow.step === 'anonymous') {
      const v = trimmed.toLowerCase();
      if (v === 'yes' || v === 'y' || v === 'no' || v === 'n') {
        setTyping(false);
        await handleChoice(v === 'yes' || v === 'y' ? 'Yes' : 'No');
        return;
      }
      await appendAssistant(
        'Reply yes or no (or use the buttons): should this stay anonymous to your manager?',
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
          <button type="button" onClick={() => setOpen(false)} className="rounded-full p-2 text-slate-500 transition hover:bg-slate-200 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        ) : null}
      </div>

      <div className={cn('flex-1 space-y-4 overflow-y-auto bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] p-5', embedded && 'min-h-[420px]')}>
        {messages.map((message) => (
          <ChatMessage key={message.id} role={message.role} text={message.text} timestamp={message.role === 'assistant' ? 'Mark' : 'You'} />
        ))}

        {typing ? (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-tl-sm bg-blue-50 px-4 py-3 text-sm text-slate-500 shadow-sm">Mark is typing...</div>
          </div>
        ) : null}

        <div ref={endRef} />
      </div>

      {control.kind !== null ? controlArea : null}
      <ChatInput value={input} onChange={setInput} onSend={() => void handleSubmit()} disabled={typing} />
    </>
  );

  if (embedded) {
    return <div className="flex h-full min-h-[520px] flex-col">{chatContent}</div>;
  }

  return (
    <>
      <motion.button
        onClick={() => setOpen(true)}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.98 }}
        className={cn('fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-600/25', open && 'hidden')}
      >
        <MessageSquare className="h-6 w-6" />
      </motion.button>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 220 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-slate-200 bg-white shadow-2xl lg:w-1/2"
          >
            {chatContent}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}