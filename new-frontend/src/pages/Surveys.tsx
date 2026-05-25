import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { createSurvey, getSurveys } from "@/lib/services";
import type { Survey } from "@/lib/domain-types";
import { SentimentBadge } from "@/components/ui-bits";
import { Plus, Sparkles, MessageSquarePlus } from "lucide-react";
import { useChat } from "@/contexts/ChatContext";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { SurveyResponseDialog } from "@/components/SurveyResponseDialog";

export default function Surveys() {
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const { open, send } = useChat();
  const { session } = useAuth();
  const [creating, setCreating] = useState(false);
  const [respondingTo, setRespondingTo] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const loadSurveys = () => {
    void getSurveys().then(setSurveys);
  };
  useEffect(() => {
    loadSurveys();
  }, []);

  // Deep link: /surveys?survey=<id> opens the fillable survey directly, so a
  // lifecycle nudge's CTA lands the user straight on the form.
  useEffect(() => {
    const id = searchParams.get("survey");
    if (id) setRespondingTo(id);
  }, [searchParams]);

  const closeResponder = () => {
    setRespondingTo(null);
    if (searchParams.has("survey")) {
      searchParams.delete("survey");
      setSearchParams(searchParams, { replace: true });
    }
  };

  const createQuickSurvey = async () => {
    setCreating(true);
    const ok = await createSurvey({
      title: `Weekly pulse (${new Date().toLocaleDateString()})`,
      description: "Auto-created pulse survey from Surveys page.",
      allow_anonymous: true,
    });
    setCreating(false);
    if (!ok) {
      toast.error("Could not create survey.");
      return;
    }
    toast.success("Survey created.");
    loadSurveys();
  };

  return (
    <AppLayout
      title="Surveys"
      subtitle="Pulse, eNPS, and check-ins — running quietly in chat"
      topbarAction={
        session?.role === "hr" || session?.role === "admin" ? (
          <button
            onClick={() => void createQuickSurvey()}
            disabled={creating}
            className="hidden md:inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-ink text-primary-foreground text-sm disabled:opacity-60"
          >
            <Plus className="size-4" /> {creating ? "Creating..." : "New survey"}
          </button>
        ) : (
          <button
            onClick={() => {
              open();
              void send("Help me design a new pulse survey");
            }}
            className="hidden md:inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-ink text-primary-foreground text-sm"
          >
            <Plus className="size-4" /> Ask MARK
          </button>
        )
      }
    >
      <div className="px-6 lg:px-10 py-8 max-w-6xl">
        <div className="rounded-2xl bg-ink text-primary-foreground p-6 relative overflow-hidden mb-8">
          <div className="absolute inset-0 bg-aurora opacity-60" />
          <div className="relative flex items-start gap-4">
            <div className="size-10 rounded-xl bg-teal-grad grid place-items-center"><Sparkles className="size-5" /></div>
            <div className="flex-1">
              <div className="text-xs uppercase tracking-[0.18em] text-primary-foreground/60">This quarter</div>
              <h3 className="font-display text-2xl mt-1">Survey intelligence from live responses.</h3>
              <p className="mt-2 text-sm text-primary-foreground/70">If surveys are not configured yet, this section will remain empty.</p>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {surveys.map(s => {
            const pct = Math.round((s.responses / Math.max(s.invited, 1)) * 100);
            return (
              <div key={s.id} className="rounded-2xl border border-border bg-card p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{s.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{s.audience}</div>
                  </div>
                  <span className={`text-[11px] px-2 py-0.5 rounded-md font-medium ${
                    s.status === "live" ? "bg-emerald-soft text-emerald" : s.status === "closed" ? "bg-secondary text-muted-foreground" : "bg-warning-soft text-warning"
                  }`}>{s.status}</span>
                </div>

                <div className="mt-5 flex items-end justify-between">
                  <div>
                    <div className="font-display text-3xl tracking-tight">{pct}%</div>
                    <div className="text-xs text-muted-foreground">{s.responses} of {s.invited} responded</div>
                  </div>
                  <SentimentBadge sentiment={s.sentiment} />
                </div>

                <div className="mt-3 h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div className="h-full bg-teal-grad" style={{ width: `${pct}%` }} />
                </div>

                {s.status === "live" && (
                  <button
                    type="button"
                    onClick={() => setRespondingTo(s.id)}
                    className="mt-4 inline-flex items-center gap-1.5 text-xs text-foreground font-medium hover:text-accent transition"
                  >
                    <MessageSquarePlus className="size-3.5" />
                    Respond now
                  </button>
                )}
              </div>
            );
          })}
          {surveys.length === 0 && (
            <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
              No surveys yet. {session?.role === "hr" || session?.role === "admin" ? "Create one to start collecting pulse data." : "Ask HR to publish a survey."}
            </div>
          )}
        </div>
      </div>

      <SurveyResponseDialog
        surveyId={respondingTo}
        onClose={closeResponder}
        onSubmitted={loadSurveys}
      />
    </AppLayout>
  );
}
