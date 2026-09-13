"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { Clock, ClipboardCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/error-banner";
import {
  getAssessment,
  startAttempt,
  listMyResponses,
  submitResponse,
  submitAttempt,
  reviewAttempt,
  type Assessment,
  type Question,
  type SavedResponse,
  type AttemptReview,
  ApiError,
} from "@/lib/api";

type Stage = "loading" | "instructions" | "in_progress" | "submitting" | "results";
type SaveStatus = "idle" | "saving" | "saved" | "error";

interface Draft {
  selected_option_ids: string[];
  response_text: string;
  marked_for_review: boolean;
}

function emptyDraft(): Draft {
  return { selected_option_ids: [], response_text: "", marked_for_review: false };
}

export default function AttemptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: assessmentId } = use(params);
  const [stage, setStage] = useState<Stage>("loading");
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, SaveStatus>>({});
  const [remainingMs, setRemainingMs] = useState<number>(0);
  const [review, setReview] = useState<AttemptReview | null>(null);

  const saveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const submittedRef = useRef(false);

  useEffect(() => {
    getAssessment(assessmentId)
      .then(setAssessment)
      .then(() => setStage("instructions"))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load"));
  }, [assessmentId]);

  const loadResults = useCallback((id: string) => {
    reviewAttempt(id)
      .then((r) => {
        setReview(r);
        setStage("results");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load results"));
  }, []);

  async function handleStart() {
    setError(null);
    try {
      const start = await startAttempt(assessmentId);
      setAttemptId(start.id);

      if (start.status !== "IN_PROGRESS") {
        loadResults(start.id);
        return;
      }

      setQuestions(start.questions);
      setDeadline(new Date(start.deadline).getTime());

      const existing = await listMyResponses(start.id);
      const nextDrafts: Record<string, Draft> = {};
      for (const q of start.questions) nextDrafts[q.id] = emptyDraft();
      for (const r of existing) {
        nextDrafts[r.question_id] = {
          selected_option_ids: r.selected_option_ids,
          response_text: r.response_text ?? "",
          marked_for_review: r.marked_for_review,
        };
      }
      setDrafts(nextDrafts);
      setStage("in_progress");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start attempt");
    }
  }

  const doSubmitAttempt = useCallback(async () => {
    if (!attemptId || submittedRef.current) return;
    submittedRef.current = true;
    setStage("submitting");
    try {
      await submitAttempt(attemptId);
    } finally {
      loadResults(attemptId);
    }
  }, [attemptId, loadResults]);

  // Countdown timer -- auto-submits the instant time runs out.
  useEffect(() => {
    if (stage !== "in_progress" || deadline === null) return;
    const tick = () => {
      const remaining = deadline - Date.now();
      setRemainingMs(Math.max(0, remaining));
      if (remaining <= 0) {
        doSubmitAttempt();
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [stage, deadline, doSubmitAttempt]);

  function saveNow(questionId: string, draft: Draft) {
    if (!attemptId) return;
    setSaveStatus((prev) => ({ ...prev, [questionId]: "saving" }));
    submitResponse(attemptId, {
      question_id: questionId,
      selected_option_ids: draft.selected_option_ids,
      response_text: draft.response_text || undefined,
      marked_for_review: draft.marked_for_review,
    })
      .then(() => setSaveStatus((prev) => ({ ...prev, [questionId]: "saved" })))
      .catch(() => setSaveStatus((prev) => ({ ...prev, [questionId]: "error" })));
  }

  function updateDraft(questionId: string, patch: Partial<Draft>, debounceMs = 0) {
    const next = { ...(drafts[questionId] ?? emptyDraft()), ...patch };
    setDrafts((prev) => ({ ...prev, [questionId]: next }));

    if (debounceMs > 0) {
      clearTimeout(saveTimers.current[questionId]);
      setSaveStatus((prev) => ({ ...prev, [questionId]: "idle" }));
      saveTimers.current[questionId] = setTimeout(() => saveNow(questionId, next), debounceMs);
    } else {
      saveNow(questionId, next);
    }
  }

  if (error) return <ErrorBanner message={error} />;

  if (stage === "loading" || assessment === null) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (stage === "instructions") {
    return (
      <div className="max-w-xl">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
            <ClipboardCheck className="size-4.5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{assessment.title}</h1>
            {assessment.description && <p className="mt-1 text-sm text-muted-foreground">{assessment.description}</p>}
          </div>
        </div>
        <Card className="mt-5 border-0 shadow-sm ring-1 ring-border">
          <CardContent className="space-y-2 py-4 text-sm">
            <p className="flex justify-between">
              <span className="text-muted-foreground">Duration</span>
              <span className="font-medium text-foreground">{assessment.duration_minutes} minutes</span>
            </p>
            <p className="flex justify-between">
              <span className="text-muted-foreground">Total marks</span>
              <span className="font-medium text-foreground">{assessment.total_marks}</span>
            </p>
            <p className="pt-1 text-xs text-muted-foreground">
              Once you start, the timer cannot be paused. The test auto-submits when time runs out.
            </p>
          </CardContent>
        </Card>
        <Button className="mt-4" onClick={handleStart}>
          Start test
        </Button>
      </div>
    );
  }

  if (stage === "submitting") {
    return <p className="text-sm text-muted-foreground">Submitting...</p>;
  }

  if (stage === "results" && review) {
    const scored = review.responses.filter((r) => r.score !== null);
    const totalScored = scored.reduce((sum, r) => sum + (r.score ?? 0), 0);
    const questionById = Object.fromEntries(review.questions.map((q) => [q.id, q]));

    return (
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Results: {assessment.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Status: {review.attempt.status} · Score so far:{" "}
          <span className="font-medium text-foreground">
            {review.attempt.total_score ?? totalScored} / {assessment.total_marks}
          </span>
        </p>

        <div className="mt-6 space-y-3">
          {review.responses.map((r) => {
            const q = questionById[r.question_id];
            if (!q) return null;
            return (
              <Card key={r.question_id} className="border-0 shadow-sm ring-1 ring-border">
                <CardContent className="py-4">
                  <p className="font-medium text-foreground">{q.question_text}</p>
                  {q.options.length > 0 && (
                    <ul className="mt-2 space-y-1 text-sm">
                      {q.options.map((o) => {
                        const selected = r.selected_option_ids.includes(o.id);
                        return (
                          <li
                            key={o.id}
                            className={
                              o.is_correct
                                ? "font-medium text-emerald-600 dark:text-emerald-400"
                                : selected
                                  ? "font-medium text-destructive"
                                  : "text-muted-foreground"
                            }
                          >
                            {selected ? "☑ " : "☐ "}
                            {o.option_text}
                            {o.is_correct ? " (correct)" : ""}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {q.options.length === 0 && r.response_text && (
                    <p className="mt-2 text-sm text-muted-foreground">Your answer: {r.response_text}</p>
                  )}
                  <p className="mt-2 text-sm">
                    {r.score === null ? (
                      <span className="text-muted-foreground">Pending manual grading</span>
                    ) : (
                      <span
                        className={
                          r.is_correct === false
                            ? "font-medium text-destructive"
                            : "font-medium text-emerald-600 dark:text-emerald-400"
                        }
                      >
                        Score: {r.score} / {q.marks}
                      </span>
                    )}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  // in_progress
  const question = questions[currentIndex];
  const draft = drafts[question.id] ?? emptyDraft();
  const status = saveStatus[question.id] ?? "idle";
  const minutes = Math.floor(remainingMs / 60000);
  const seconds = Math.floor((remainingMs % 60000) / 1000);
  const lowTime = remainingMs < 60000;

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between gap-4">
        <h1 className="truncate text-xl font-semibold tracking-tight text-foreground">{assessment.title}</h1>
        <div
          className={`flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium tabular-nums ${
            lowTime ? "bg-destructive/10 text-destructive" : "bg-secondary text-secondary-foreground"
          }`}
        >
          <Clock className="size-3.5" />
          {minutes}:{seconds.toString().padStart(2, "0")}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-primary" /> Current
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-emerald-500/70" /> Answered
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-amber-500/70" /> Marked for review
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-muted" /> Unanswered
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {questions.map((q, i) => {
          const d = drafts[q.id];
          const answered = d && (d.selected_option_ids.length > 0 || d.response_text.trim().length > 0);
          return (
            <button
              key={q.id}
              onClick={() => setCurrentIndex(i)}
              className={`flex h-8 w-8 items-center justify-center rounded-md text-xs font-medium transition-colors ${
                i === currentIndex
                  ? "bg-primary text-primary-foreground"
                  : d?.marked_for_review
                    ? "bg-amber-500/20 text-foreground"
                    : answered
                      ? "bg-emerald-500/20 text-foreground"
                      : "bg-muted text-muted-foreground"
              }`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      <Card className="mt-4 border-0 shadow-sm ring-1 ring-border">
        <CardContent className="py-4">
          <p className="text-sm text-muted-foreground">
            Question {currentIndex + 1} of {questions.length} · {question.marks} marks
          </p>
          <p className="mt-2 font-medium text-foreground">{question.question_text}</p>

          <div className="mt-4 space-y-2">
            {question.question_type === "MCQ" || question.question_type === "TRUE_FALSE"
              ? question.options.map((opt) => (
                  <label key={opt.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name={question.id}
                      checked={draft.selected_option_ids[0] === opt.id}
                      onChange={() => updateDraft(question.id, { selected_option_ids: [opt.id] })}
                    />
                    {opt.option_text}
                  </label>
                ))
              : null}

            {question.question_type === "MULTI_SELECT" &&
              question.options.map((opt) => (
                <label key={opt.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.selected_option_ids.includes(opt.id)}
                    onChange={() => {
                      const set = new Set(draft.selected_option_ids);
                      if (set.has(opt.id)) set.delete(opt.id);
                      else set.add(opt.id);
                      updateDraft(question.id, { selected_option_ids: Array.from(set) });
                    }}
                  />
                  {opt.option_text}
                </label>
              ))}

            {question.question_type === "NUMERICAL" && (
              <Input
                type="number"
                step="any"
                value={draft.response_text}
                onChange={(e) => updateDraft(question.id, { response_text: e.target.value }, 600)}
              />
            )}

            {(question.question_type === "SHORT_ANSWER" || question.question_type === "LONG_ANSWER") && (
              <Textarea
                rows={question.question_type === "LONG_ANSWER" ? 8 : 3}
                value={draft.response_text}
                onChange={(e) => updateDraft(question.id, { response_text: e.target.value }, 600)}
              />
            )}
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={draft.marked_for_review}
                onChange={(e) => updateDraft(question.id, { marked_for_review: e.target.checked })}
              />
              Mark for review
            </label>
            <span className="text-xs text-muted-foreground">
              {status === "saving" && "Saving..."}
              {status === "saved" && "Saved"}
              {status === "error" && "Save failed"}
            </span>
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 flex items-center justify-between">
        <div className="flex gap-2">
          <Button variant="outline" disabled={currentIndex === 0} onClick={() => setCurrentIndex((i) => i - 1)}>
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={currentIndex === questions.length - 1}
            onClick={() => setCurrentIndex((i) => i + 1)}
          >
            Next
          </Button>
        </div>
        <Button
          variant="destructive"
          onClick={() => {
            if (confirm("Submit the test now? You cannot change your answers after this.")) {
              doSubmitAttempt();
            }
          }}
        >
          Submit test
        </Button>
      </div>
    </div>
  );
}
