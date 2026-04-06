"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CalendarDays, FileText, MessageSquare, Upload } from 'lucide-react';
import { ChatPanel } from '@/components/ChatPanel';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';

export default function EmployeePage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  useEffect(() => {
    if (authLoading) return;

    if (session?.role === 'hr') {
      router.replace('/dashboard');
    }
  }, [authLoading, session, router]);

  if (authLoading) {
    return <Spinner message="Verifying authentication..." />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#eff6ff,transparent_34%),linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] px-6 py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr] lg:items-end">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600">Employee experience</p>
            <h1 className="text-4xl font-semibold tracking-tight text-slate-900 md:text-5xl">Talk to Mark first.</h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600">
              Employees use the chat to raise complaints, apply for leave, ask policies, and upload context. The conversation is intentionally minimal and step-by-step.
            </p>
          </div>

          <Card className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
            <CardHeader>
              <CardTitle className="text-xl">What you can do here</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {[
                { icon: MessageSquare, title: 'Raise complaints', text: 'Start a ticket in chat and keep it confidential when needed.' },
                { icon: CalendarDays, title: 'Apply leave', text: 'Mark asks for dates one step at a time and fills the request.' },
                { icon: FileText, title: 'Ask policies', text: 'Get quick answers from the company handbook and benefits docs.' },
                { icon: Upload, title: 'Upload context', text: 'Attach documents or details when the workflow needs supporting info.' },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <h2 className="text-sm font-semibold text-slate-900">{item.title}</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{item.text}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <section className="min-h-[560px] rounded-[2rem] border border-slate-200 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.1)]">
          <div className="border-b border-slate-100 px-6 py-4">
            <p className="text-sm font-semibold text-slate-900">Chat with Mark</p>
            <p className="text-sm text-slate-500">One question at a time. No forms unless the flow needs them.</p>
          </div>
          <div className="relative min-h-[480px]">
            <ChatPanel embedded />
          </div>
        </section>
      </div>
    </div>
  );
}