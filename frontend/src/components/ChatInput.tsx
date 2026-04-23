"use client";

import { FormEvent, useRef } from 'react';
import { Send, Paperclip, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface SelectedFile {
  name: string;
  size: number;
  file: File;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  placeholder?: string;
  disabled?: boolean;
  selectedFile?: SelectedFile | null;
  onFileChange?: (file: SelectedFile | null) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ChatInput({ value, onChange, onSend, placeholder = 'Reply to Mark...', disabled, selectedFile, onFileChange }: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSend();
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && onFileChange) {
      onFileChange({
        name: file.name,
        size: file.size,
        file,
      });
    }
    event.target.value = '';
  };

  const handleRemoveFile = () => {
    if (onFileChange) {
      onFileChange(null);
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white p-4">
      {selectedFile ? (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <Paperclip className="h-4 w-4 flex-shrink-0 text-slate-500" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-700">{selectedFile.name}</p>
            <p className="text-xs text-slate-500">{formatFileSize(selectedFile.size)}</p>
          </div>
          <button
            type="button"
            onClick={handleRemoveFile}
            className="flex-shrink-0 rounded-full p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : null}
      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileSelect}
          accept="*/*"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-10 w-10 flex-shrink-0 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
        >
          <Paperclip className="h-4 w-4" />
        </Button>
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
    </div>
  );
}