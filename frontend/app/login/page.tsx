"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Lock, Mail, Shield, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/spinner';

export default function LoginPage() {
  const router = useRouter();
  const { loading: authLoading, login } = useAuth();
  const [email, setEmail] = useState('employee@mark.ai');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (authLoading) {
    return <Spinner message="Verifying authentication..." />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await login(email, password);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to sign in');
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#eff6ff,transparent_34%),linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] px-6 py-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-7xl gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
        <section className="space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 shadow-sm">
            <Sparkles className="h-4 w-4" />
            Secure access for employees and HR
          </div>
          <div className="space-y-4">
            <h1 className="text-5xl font-semibold tracking-tight text-slate-900 md:text-6xl">Role-based AI HR platform</h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600">
              Sign in once and Mark routes you to the right experience. Employees get a chat-first assistant. HR gets dashboards, sentiment, and ticket control.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
              <CardHeader>
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <Shield className="h-6 w-6" />
                </div>
                <CardTitle className="text-xl">Employee login</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-slate-600">Employees use Mark to chat, raise tickets, and ask questions.</CardContent>
            </Card>

            <Card className="border-slate-200 bg-white/90 shadow-sm backdrop-blur">
              <CardHeader>
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
                  <Lock className="h-6 w-6" />
                </div>
                <CardTitle className="text-xl">HR admin login</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-slate-600">HR users land in the dashboard with tickets, sentiment, and control.</CardContent>
            </Card>
          </div>
        </section>

        <Card className="mx-auto w-full max-w-xl border-slate-200 bg-white/95 shadow-[0_30px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <CardHeader className="space-y-3 border-b border-slate-100 pb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Authentication</p>
            <CardTitle className="text-3xl font-semibold text-slate-900">Sign in to Mark</CardTitle>
            <p className="text-sm leading-6 text-slate-600">The role comes from the Supabase users table and controls the redirect after login.</p>
          </CardHeader>

          <CardContent className="space-y-6 pt-6">
            <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input value={email} onChange={(event) => setEmail(event.target.value)} className="h-12 rounded-2xl bg-slate-50 pl-10" placeholder="name@company.com" type="email" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Password</label>
                <Input value={password} onChange={(event) => setPassword(event.target.value)} className="h-12 rounded-2xl bg-slate-50" placeholder="Password" type="password" />
              </div>

              {error ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}

              <Button type="submit" className="h-12 w-full rounded-full" disabled={loading}>
                {loading ? 'Signing in...' : 'Sign in'}
              </Button>
            </form>

            <p className="text-center text-xs leading-5 text-slate-500">
              Role is resolved from Supabase after authentication. If the environment is not connected, the frontend falls back to the selected demo role.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}