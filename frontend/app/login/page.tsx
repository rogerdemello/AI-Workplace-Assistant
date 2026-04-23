"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Lock, Mail, Shield, Sparkles, Zap } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';

export default function LoginPage() {
  const router = useRouter();
  const { loading: authLoading, login } = useAuth();
  const [email, setEmail] = useState('employee@mark.ai');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (authLoading) return <Spinner message="Verifying authentication..." />;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in');
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0a0a1a]">
      {/* Background orbs */}
      <div className="orb orb-violet w-96 h-96 -top-24 -left-24" />
      <div className="orb orb-indigo w-80 h-80 top-1/3 -right-20" />
      <div className="orb orb-pink w-64 h-64 bottom-0 left-1/3" />

      <div className="relative z-10 min-h-screen flex items-center px-6 py-16">
        <div className="mx-auto grid w-full max-w-6xl gap-16 lg:grid-cols-[1fr_480px] lg:items-center">

          {/* ── Left: Brand panel ────────────────────────────── */}
          <section className="animate-fade-up space-y-10 text-white">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-medium text-white/70">
              <Sparkles className="h-4 w-4 text-violet-400" />
              AI-Powered HR Operating System
            </div>

            <div className="space-y-5">
              <h1 className="text-5xl font-bold leading-[1.1] md:text-6xl">
                Meet{' '}
                <span className="text-brand-gradient">Mark</span>.
                <br />
                Your AI HR
                <br />
                Partner.
              </h1>
              <p className="max-w-xl text-lg leading-8 text-white/60">
                Conversational workflows for employees. Real-time intelligence for HR.
                One platform, zero friction.
              </p>
            </div>

            {/* Feature pills */}
            <div className="flex flex-wrap gap-3">
              {[
                { icon: Shield, text: 'Complaint tickets in 3 steps' },
                { icon: Zap, text: 'Sentiment-aware responses' },
                { icon: Sparkles, text: 'Live HR dashboard' },
              ].map(({ icon: Icon, text }) => (
                <div
                  key={text}
                  className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-white/70"
                >
                  <Icon className="h-3.5 w-3.5 text-violet-400" />
                  {text}
                </div>
              ))}
            </div>

            {/* Role legend */}
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  icon: Shield,
                  title: 'Employee',
                  desc: 'Chat with Mark to raise tickets, apply leave, and ask policies.',
                  color: 'text-indigo-400',
                  bg: 'bg-indigo-500/10 border-indigo-500/20',
                },
                {
                  icon: Lock,
                  title: 'HR Admin',
                  desc: 'Dashboard with sentiment trends, risk scores, and ticket management.',
                  color: 'text-violet-400',
                  bg: 'bg-violet-500/10 border-violet-500/20',
                },
              ].map(({ icon: Icon, title, desc, color, bg }) => (
                <div key={title} className={`rounded-2xl border p-5 ${bg}`}>
                  <Icon className={`mb-3 h-5 w-5 ${color}`} />
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="mt-1 text-xs leading-5 text-white/50">{desc}</p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Right: Login card ─────────────────────────────── */}
          <div
            className="animate-scale-in glass rounded-3xl p-8 shadow-2xl"
            style={{ animationDelay: '0.1s' }}
          >
            <div className="mb-8 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                Secure authentication
              </p>
              <h2 className="text-2xl font-bold text-slate-900">Sign in to Mark</h2>
              <p className="text-sm text-slate-500">
                Your role determines the experience after login.
              </p>
            </div>

            <form className="space-y-5" onSubmit={(e) => void handleSubmit(e)}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="h-12 rounded-2xl bg-slate-50 pl-10 focus:ring-2 focus:ring-violet-400"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    className="h-12 rounded-2xl bg-slate-50 pl-10 focus:ring-2 focus:ring-violet-400"
                  />
                </div>
              </div>

              {error && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {error}
                </div>
              )}

              <Button
                id="login-submit"
                type="submit"
                disabled={loading}
                className="h-12 w-full rounded-2xl bg-brand-gradient font-semibold text-white shadow-lg shadow-violet-500/25 hover:opacity-90 transition-opacity"
              >
                {loading ? 'Signing in…' : 'Sign in to Mark →'}
              </Button>
            </form>

            <p className="mt-6 text-center text-xs text-slate-400">
              Role is resolved from your account after authentication.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}