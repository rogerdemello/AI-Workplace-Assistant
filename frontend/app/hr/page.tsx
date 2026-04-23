import Link from 'next/link';

export default function HrPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">HR Workspace</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">HR landing page</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          This route is used as a lightweight HR entry point for redirected flows.
          Use the links below to continue into operational views.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/dashboard"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Open dashboard
          </Link>
          <Link
            href="/employee"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Open employee view
          </Link>
          <Link
            href="/tickets"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Open tickets
          </Link>
        </div>
      </div>
    </main>
  );
}
