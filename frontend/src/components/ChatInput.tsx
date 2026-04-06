"use client";

import { FormEvent } from 'react';
import { Send } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  placeholder?: string;
  disabled?: boolean;
}

export function ChatInput({ value, onChange, onSend, placeholder = 'Reply to Mark...', disabled }: ChatInputProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSend();
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3 border-t border-slate-200 bg-white p-4">
      <div className="relative flex-1">
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="h-12 rounded-full border-slate-200 bg-slate-50 pr-12"
        />
        <Button type="submit" size="icon" className="absolute right-1 top-1 h-10 w-10 rounded-full" disabled={disabled}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}