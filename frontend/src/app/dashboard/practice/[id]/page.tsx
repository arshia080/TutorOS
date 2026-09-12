"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getPracticeSet,
  submitPracticeResponse,
  completePracticeSet,
  type PracticeSet,
  type PracticeCompletion,
  ApiError,
} from "@/lib/api";

type Stage = "loading" | "in_progress" | "completed";

interface Draft {
  selected_option_id?: string;
  response_text?: string;
}

export default function PracticePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("loading");
  const [practiceSet, setPracticeSet] = useState<PracticeSet | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, "idle" | "saving" | "saved">>({});
  const [completion, setCompletion] = useState<PracticeCompletion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    getPracticeSet(id)
      .then((ps) => {
        if (ps.status === "COMPLETED") {
          return completePracticeSet(id).then((c) => {
            setCompletion(c);
            setStage("completed");
          });
        }
        setPracticeSet(ps);
        setStage("in_progress");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load practice set"));
  }, [id]);

  async function handleAnswer(questionId: string, draft: Draft) {
    setDrafts((prev) => ({ ...prev, [questionId]: draft }));
    setSaveStatus((prev) => ({ ...prev, [questionId]: "saving" }));
    try {
      await submitPracticeResponse(id, { question_id: questionId, ...draft });
      setSaveStatus((prev) => ({ ...prev, [questionId]: "saved" }));
    } catch {
      setSaveStatus((prev) => ({ ...prev, [questionId]: "idle" }));
    }
  }

  async function handleFinish() {
    setError(null);
    setFinishing(true);
    try {
      const result = await completePracticeSet(id);
      setCompletion(result);
      setStage("completed");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to finish practice");
    } finally {
      setFinishing(false);
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;

  if (stage === "loading") {
    return <Skeleton className="h-64 w-full" />;
  }

  if (stage === "completed" && completion) {
    const improved = completion.delta > 0;
    return (
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold">Practice results: {completion.practice_set.topic_name}</h1>

        <Card className="mt-4">
          <CardContent className="py-4">
            <div className="flex items-center gap-6">
              <div>
                <p className="text-sm text-muted-foreground">Before</p>
                <p className="text-2xl font-semibold">{completion.mastery_before}%</p>
              </div>
              <div className="text-2xl text-muted-foreground">→</div>
              <div>
                <p className="text-sm text-muted-foreground">After</p>
                <p className="text-2xl font-semibold">{completion.mastery_after}%</p>
              </div>
              <Badge variant={improved ? "default" : "secondary"}>
                {improved ? "+" : ""}
                {completion.delta}pp
              </Badge>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{completion.note}</p>
          </CardContent>
        </Card>

        <div className="mt-6 space-y-2">
          {completion.responses.map((r, i) => (
            <Card key={r.question_id}>
              <CardContent className="flex items-center justify-between py-3">
                <p className="text-sm">Question {i + 1}</p>
                <Badge variant={r.is_correct ? "default" : "destructive"}>{r.is_correct ? "Correct" : "Incorrect"}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        <Button className="mt-4" variant="outline" onClick={() => router.push("/dashboard")}>
          Back to dashboard
        </Button>
      </div>
    );
  }

  if (!practiceSet) return null;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">Practice: {practiceSet.topic_name}</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {practiceSet.questions.length} questions -- no time limit, answer at your own pace.
      </p>

      <div className="mt-6 space-y-4">
        {practiceSet.questions.map((q, i) => {
          const draft = drafts[q.id] ?? {};
          const status = saveStatus[q.id] ?? "idle";
          return (
            <Card key={q.id}>
              <CardContent className="py-4">
                <p className="text-sm text-muted-foreground">
                  Question {i + 1} · {q.difficulty}
                </p>
                <p className="mt-1 font-medium">{q.question_text}</p>

                <div className="mt-3 space-y-2">
                  {(q.question_type === "MCQ" || q.question_type === "TRUE_FALSE") &&
                    q.options.map((opt) => (
                      <label key={opt.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name={q.id}
                          checked={draft.selected_option_id === opt.id}
                          onChange={() => handleAnswer(q.id, { selected_option_id: opt.id })}
                        />
                        {opt.option_text}
                      </label>
                    ))}
                  {q.question_type === "NUMERICAL" && (
                    <Input
                      type="number"
                      step="any"
                      value={draft.response_text ?? ""}
                      onChange={(e) => handleAnswer(q.id, { response_text: e.target.value })}
                    />
                  )}
                </div>

                {status === "saved" && <p className="mt-2 text-xs text-muted-foreground">Saved</p>}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      <Button className="mt-4" onClick={handleFinish} disabled={finishing || Object.keys(drafts).length === 0}>
        {finishing ? "Finishing..." : "Finish Practice"}
      </Button>
    </div>
  );
}
