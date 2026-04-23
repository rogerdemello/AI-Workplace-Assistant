"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type ToastVariant = 'success' | 'error' | 'info';

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
  durationMs?: number;
}

interface ToastContextValue {
  showToast: (toast: ToastInput) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function shortId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timerMapRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timerMapRef.current[id];
    if (timer) {
      clearTimeout(timer);
      delete timerMapRef.current[id];
    }
  }, []);

  const showToast = useCallback(
    (toast: ToastInput) => {
      const id = shortId();
      const next: ToastItem = {
        id,
        title: toast.title,
        description: toast.description,
        variant: toast.variant ?? 'info',
      };

      setToasts((current) => [...current, next]);
      const durationMs = Math.max(1200, toast.durationMs ?? 3800);
      timerMapRef.current[id] = setTimeout(() => {
        dismissToast(id);
      }, durationMs);
    },
    [dismissToast]
  );

  useEffect(() => {
    return () => {
      Object.values(timerMapRef.current).forEach((timer) => clearTimeout(timer));
      timerMapRef.current = {};
    };
  }, []);

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}
      <div
        aria-live="polite"
        data-testid="toast-region"
        className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            data-testid={`toast-${toast.variant}`}
            className={cn(
              'pointer-events-auto rounded-2xl border bg-white px-4 py-3 shadow-lg',
              toast.variant === 'success' && 'border-emerald-200 text-emerald-800',
              toast.variant === 'error' && 'border-rose-200 text-rose-800',
              toast.variant === 'info' && 'border-blue-200 text-blue-800'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.description ? <p className="mt-1 text-xs opacity-90">{toast.description}</p> : null}
              </div>
              <button
                type="button"
                className="rounded-full px-2 py-0.5 text-xs opacity-80 hover:bg-black/5"
                onClick={() => dismissToast(toast.id)}
              >
                Close
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}