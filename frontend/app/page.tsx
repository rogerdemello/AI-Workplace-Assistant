"use client";

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, BarChart3, Bot, FileText, MessageSquare, Shield, Sparkles, Ticket, UserCheck, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const features = [
  {
    icon: Workflow,
    title: 'Smart Workflows',
    description: 'Handle leave requests, policy answers, and complaints in one conversational layer.',
  },
  {
    icon: Ticket,
    title: 'Ticketing System',
    description: 'Turn employee conversations into structured, trackable HR work.',
  },
  {
    icon: BarChart3,
    title: 'People Analytics',
    description: 'See engagement, risk, and response trends in one place.',
  },
  {
    icon: Shield,
    title: 'Sentiment Tracking',
    description: 'Follow morale across messages and spot risk before it spreads.',
  },
  {
    icon: FileText,
    title: 'Document AI',
    description: 'Let Mark answer policies directly from your knowledge base.',
  },
  {
    icon: UserCheck,
    title: 'Proactive Check-ins',
    description: 'Nudge employees and managers when important moments or risk signals appear.',
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#eff6ff,transparent_34%),linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)]">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/25">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-blue-600">Mark</p>
            <p className="text-sm text-slate-500">AI Chief People Officer</p>
          </div>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <Link href="/login?role=employee">
            <Button variant="outline" className="rounded-full border-slate-200 bg-white px-5">
              Employee Login
            </Button>
          </Link>
          <Link href="/login?role=hr">
            <Button className="rounded-full px-5">
              HR Login
            </Button>
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-14 px-6 py-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-20">
        <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-3xl space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 shadow-sm">
            <Sparkles className="h-4 w-4" />
            Human-like HR support for every employee conversation
          </div>

          <div className="space-y-5">
            <h1 className="text-5xl font-semibold tracking-tight text-slate-900 md:text-6xl">
              AI Chief People Officer
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600 md:text-xl">
              Mark is the employee-facing assistant and HR intelligence layer for modern teams. Employees chat first. HR gets the tickets, sentiment, and insight that matter.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/login?role=employee">
              <Button size="lg" className="h-12 rounded-full px-6 shadow-lg shadow-blue-600/20">
                Open Assistant
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login?role=hr">
              <Button size="lg" variant="outline" className="h-12 rounded-full border-slate-200 bg-white px-6">
                HR Dashboard Login
              </Button>
            </Link>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {[
              ['Employee-first', 'Chat is the primary interface'],
              ['HR-ready', 'Tickets and sentiment flow into the dashboard'],
              ['Role-based', 'Separate employee and HR experiences'],
            ].map(([title, text]) => (
              <Card key={title} className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-slate-900">{title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm leading-6 text-slate-600">{text}</CardContent>
              </Card>
            ))}
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="relative">
          <div className="absolute -left-6 -top-6 h-24 w-24 rounded-full bg-blue-200/40 blur-2xl" />
          <div className="absolute -bottom-8 right-2 h-28 w-28 rounded-full bg-cyan-200/40 blur-2xl" />

          <div className="relative overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.12)]">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Live preview</p>
                <h2 className="text-lg font-semibold text-slate-900">Mark chat</h2>
              </div>
              <div className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Online</div>
            </div>

            <div className="space-y-4 bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] p-6">
              <div className="flex items-start gap-3">
                <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">A</div>
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-blue-600 px-4 py-3 text-sm text-white shadow-sm">
                  Hey. I have been feeling overwhelmed by the current project timeline.
                </div>
              </div>
              <div className="flex items-start justify-end gap-3">
                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-slate-200 px-4 py-3 text-sm text-slate-900 shadow-sm">
                  That sounds frustrating. Want me to raise this with HR and keep it confidential?
                </div>
                <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-white">U</div>
              </div>
              <div className="flex items-start gap-3">
                <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">A</div>
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-blue-100 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                  I can help with that step by step. Please tell me whether you want this logged as a complaint, leave request, or general HR question.
                </div>
              </div>
            </div>
          </div>
        </motion.section>
      </main>

      <section className="mx-auto max-w-7xl px-6 py-8 md:py-16">
        <div className="mb-8 max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-blue-600">Product capabilities</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 md:text-4xl">Designed for B2B HR operations</h2>
          <p className="mt-3 text-lg leading-8 text-slate-600">
            The interface is split by role: employees get a focused assistant, and HR gets the analytics and work queues.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title} className="border-slate-200 bg-white/90 shadow-sm backdrop-blur transition hover:-translate-y-1 hover:shadow-lg">
              <CardHeader className="space-y-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <feature.icon className="h-6 w-6" />
                </div>
                <CardTitle className="text-xl text-slate-900">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-slate-600">{feature.description}</CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-200 bg-slate-900 py-16 text-white">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 md:flex-row md:items-center">
          <div className="max-w-2xl space-y-3">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-blue-300">Get started</p>
            <h2 className="text-3xl font-semibold md:text-4xl">Two roles. One system. Clear separation.</h2>
            <p className="text-white/70">
              Employees start in chat. HR logs in to a dashboard with tickets, sentiment, and employee insights.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/login?role=employee">
              <Button className="rounded-full bg-white px-6 text-slate-900 hover:bg-slate-100">
                Employee Login
              </Button>
            </Link>
            <Link href="/login?role=hr">
              <Button variant="outline" className="rounded-full border-white/20 bg-white/10 px-6 text-white hover:bg-white/20">
                HR Login
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
