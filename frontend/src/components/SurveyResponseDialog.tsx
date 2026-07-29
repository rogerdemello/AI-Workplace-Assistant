import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { getSurveyDetail, submitSurveyResponse, type SurveyDetail, type SurveyQuestionDetail } from "@/lib/api/work";
import { toast } from "sonner";

interface Props {
  surveyId: string | null;
  onClose: () => void;
  onSubmitted: () => void;
}

export function SurveyResponseDialog({ surveyId, onClose, onSubmitted }: Props) {
  const [survey, setSurvey] = useState<SurveyDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [anonymous, setAnonymous] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!surveyId) {
      setSurvey(null);
      setAnswers({});
      return;
    }
    setLoading(true);
    void getSurveyDetail(surveyId).then((detail) => {
      setLoading(false);
      if (!detail) {
        toast.error("Could not load survey.");
        onClose();
        return;
      }
      setSurvey(detail);
      setAnswers({});
    });
  }, [surveyId, onClose]);

  const setAnswer = (questionId: string, value: unknown) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const validate = (): string | null => {
    if (!survey) return "Survey unavailable.";
    for (const q of survey.questions) {
      if (q.required === false) continue;
      const value = answers[q.id];
      if (value == null || (typeof value === "string" && !value.trim())) {
        return `Please answer: ${q.question}`;
      }
    }
    return null;
  };

  const handleSubmit = async () => {
    if (!survey) return;
    const error = validate();
    if (error) {
      toast.error(error);
      return;
    }
    setSubmitting(true);
    const ok = await submitSurveyResponse(survey.id, answers, anonymous && survey.allow_anonymous);
    setSubmitting(false);
    if (!ok) {
      toast.error("Could not submit your response. Please try again.");
      return;
    }
    toast.success("Thanks — your response was recorded.");
    onSubmitted();
    onClose();
  };

  return (
    <Dialog open={Boolean(surveyId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{survey?.title ?? "Survey"}</DialogTitle>
          {survey?.description && <DialogDescription>{survey.description}</DialogDescription>}
        </DialogHeader>

        {loading && <div className="text-sm text-muted-foreground py-6">Loading questions…</div>}

        {survey && !loading && (
          <div className="space-y-5 py-2">
            {survey.questions.length === 0 && (
              <div className="text-sm text-muted-foreground">
                This survey has no questions configured yet.
              </div>
            )}
            {survey.questions.map((q) => (
              <QuestionField
                key={q.id}
                question={q}
                value={answers[q.id]}
                onChange={(value) => setAnswer(q.id, value)}
              />
            ))}
            {survey.allow_anonymous && (
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={anonymous}
                  onChange={(e) => setAnonymous(e.target.checked)}
                  className="size-4 rounded border-border"
                />
                Submit anonymously
              </label>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting || !survey || survey.questions.length === 0}>
            {submitting ? "Submitting…" : "Submit response"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: SurveyQuestionDetail;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const required = question.required !== false;

  if (question.type === "rating") {
    const numeric = typeof value === "number" ? value : null;
    return (
      <div className="space-y-2">
        <Label className="text-sm">
          {question.question} {required && <span className="text-danger">*</span>}
        </Label>
        <div className="flex flex-wrap gap-1.5">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              className={`size-9 rounded-md border text-sm font-medium transition ${
                numeric === n
                  ? "bg-ink text-primary-foreground border-ink"
                  : "border-border bg-card hover:bg-secondary"
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (question.type === "choice" && question.options?.length) {
    return (
      <div className="space-y-2">
        <Label className="text-sm">
          {question.question} {required && <span className="text-danger">*</span>}
        </Label>
        <div className="space-y-1.5">
          {question.options.map((opt) => (
            <label key={opt} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={question.id}
                checked={value === opt}
                onChange={() => onChange(opt)}
                className="size-4"
              />
              {opt}
            </label>
          ))}
        </div>
      </div>
    );
  }

  if (question.type === "multiple_choice" && question.options?.length) {
    const selected = Array.isArray(value) ? (value as string[]) : [];
    return (
      <div className="space-y-2">
        <Label className="text-sm">
          {question.question} {required && <span className="text-danger">*</span>}
        </Label>
        <div className="space-y-1.5">
          {question.options.map((opt) => {
            const checked = selected.includes(opt);
            return (
              <label key={opt} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const next = checked ? selected.filter((s) => s !== opt) : [...selected, opt];
                    onChange(next);
                  }}
                  className="size-4"
                />
                {opt}
              </label>
            );
          })}
        </div>
      </div>
    );
  }

  // Default: short or long text
  const stringValue = typeof value === "string" ? value : "";
  const isLong = question.type === "longtext" || question.question.length > 60;
  return (
    <div className="space-y-2">
      <Label className="text-sm">
        {question.question} {required && <span className="text-danger">*</span>}
      </Label>
      {isLong ? (
        <Textarea
          value={stringValue}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          placeholder="Type your answer…"
        />
      ) : (
        <Input
          value={stringValue}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Type your answer…"
        />
      )}
    </div>
  );
}
