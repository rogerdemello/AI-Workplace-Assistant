"use client";

import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { listHrAlerts, runHrAlertScan, type HrAlertItem } from '@/lib/api';

export function HrAlertsCard() {
  const [alerts, setAlerts] = useState<HrAlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listHrAlerts(20);
      setAlerts(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load alerts");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runScan = async () => {
    setScanning(true);
    setError(null);
    try {
      const res = await runHrAlertScan();
      if (!res.ok && res.error) {
        setError(res.error);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle>Proactive alerts</CardTitle>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" className="rounded-full" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
          <Button type="button" size="sm" className="rounded-full" onClick={() => void runScan()} disabled={scanning}>
            {scanning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Run scan now
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-slate-500">
          Background job stores wellbeing scans (daily by default). Use &quot;Run scan now&quot; to refresh without waiting.
        </p>
        {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</div> : null}
        {loading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : alerts.length === 0 ? (
          <p className="text-sm text-slate-500">No alerts yet. Run a scan after employees have chat activity.</p>
        ) : (
          <ul className="space-y-2">
            {alerts.map((a) => (
              <li
                key={a.id}
                className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
              >
                <span className="font-medium text-slate-900">{a.title}</span>
                <span className="ml-2 text-xs uppercase text-slate-400">{a.severity}</span>
                <p className="mt-1 text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
