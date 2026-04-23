"use client";

import { useCallback, useEffect, useState } from 'react';
import { Heart, Loader2, MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getAllAppreciations, type AppreciationResponse } from '@/lib/api';

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function AppreciationItem({ note }: { note: AppreciationResponse }) {
  return (
    <div className="group relative rounded-2xl border border-slate-100 bg-white p-4 shadow-sm transition-all hover:border-blue-200 hover:shadow-md">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-rose-100 to-pink-100">
          <Heart className="h-5 w-5 text-rose-500" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-slate-900">{note.is_anonymous ? 'Anonymous' : 'Team member'}</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-600 line-clamp-2">{note.message}</p>
          <p className="mt-2 text-xs text-slate-400">{formatTimeAgo(note.created_at)}</p>
        </div>
      </div>
    </div>
  );
}

function AllAppreciationsModal({
  notes,
  onClose,
}: {
  notes: AppreciationResponse[];
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl max-h-[80vh] overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">All Appreciation Notes</h2>
          <Button variant="ghost" size="sm" className="rounded-full" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="overflow-y-auto p-6" style={{ maxHeight: 'calc(80vh - 80px)' }}>
          {notes.length === 0 ? (
            <p className="text-center text-sm text-slate-500">No appreciation notes yet.</p>
          ) : (
            <div className="space-y-3">
              {notes.map((note) => (
                <AppreciationItem key={note.id} note={note} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function AppreciationCard() {
  const [notes, setNotes] = useState<AppreciationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllAppreciations(50);
      setNotes(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load appreciations');
      setNotes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const recentNotes = notes.slice(0, 4);
  const totalCount = notes.length;

  return (
    <>
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <Heart className="h-5 w-5 text-rose-500" />
            Team Appreciation
          </CardTitle>
          {totalCount > 4 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full"
              onClick={() => setShowAll(true)}
            >
              <MoreHorizontal className="mr-1 h-4 w-4" />
              View all ({totalCount})
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-slate-500">
            Recent shout-outs and appreciation notes from employees.
          </p>
          {error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {error}
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : recentNotes.length === 0 ? (
            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-6 text-center">
              <Heart className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm text-slate-500">No appreciation notes yet.</p>
              <p className="text-xs text-slate-400">Notes will appear when employees send shout-outs.</p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {recentNotes.map((note) => (
                <AppreciationItem key={note.id} note={note} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {showAll && <AllAppreciationsModal notes={notes} onClose={() => setShowAll(false)} />}
    </>
  );
}