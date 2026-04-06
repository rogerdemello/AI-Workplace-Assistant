"use client";

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

export interface ChatMessageProps {
  role: 'user' | 'assistant';
  text: string;
  timestamp?: string;
}

export function ChatMessage({ role, text, timestamp }: ChatMessageProps) {
  const body = text?.trim();
  if (!body) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex w-full', role === 'user' ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
          role === 'user'
            ? 'rounded-tr-sm bg-slate-200 text-slate-900'
            : 'rounded-tl-sm bg-blue-600 text-white'
        )}
      >
        <p className="whitespace-pre-wrap">{body}</p>
        {timestamp ? <p className={cn('mt-1 text-[11px]', role === 'user' ? 'text-slate-500' : 'text-white/70')}>{timestamp}</p> : null}
      </div>
    </motion.div>
  );
}