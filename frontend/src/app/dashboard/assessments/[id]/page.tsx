"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getAssessment,
  listQuestions,
  deleteQuestion,
  publishAssessment,
  closeAssessment,
  type Assessment,
  type Question,
  ApiError,
} from "@/lib/api";
import { QuestionForm } from "./question-form";

export default function AssessmentBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [publishErrors, setPublishErrors] = useState<string[] | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [showForm, setShowForm] = useState(false);

  function load() {
    setError(null);
    Promise.all([getAssessment(id), listQuestions(id)])
      .then(([a, qs]) => {
        setAssessment(a);
        setQuestions(qs);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load assessment"));
  }

  useEffect(load, [id]);

  const editable = assessment?.status === "DRAFT" || assessment?.status === "REVIEW";
  const questionMarksTotal = questions?.reduce((sum, q) => sum + q.marks, 0) ?? 0;

  async function handlePublish() {
    setPublishErrors(null);
    setPublishing(true);
    try {
      const updated = await publishAssessment(id);
      setAssessment(updated);
    } catch (err) {
      if (err instanceof ApiError && err.details) setPublishErrors(err.details);
      else setPublishErrors([err instanceof ApiError ? err.message : "Failed to publish"]);
    } finally {
      setPublishing(false);
    }
  }

  async function handleClose() {
    const updated = await closeAssessment(id);
    setAssessment(updated);
  }

  async function handleDelete(questionId: string) {
    await deleteQuestion(id, questionId);
    load();
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;

  if (assessment === null) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{assessment.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {assessment.duration_minutes} min · {assessment.total_marks} marks declared ·{" "}
            {questionMarksTotal} marks from questions so far
          </p>
        </div>
        <Badge>{assessment.status}</Badge>
      </div>

      <div className="mt-4 flex gap-2">
        {assessment.status === "PUBLISHED" && (
          <>
            <Link href={`/dashboard/assessments/${id}/attempts`}>
              <Button variant="outline">View attempts</Button>
            </Link>
            <Button variant="destructive" onClick={handleClose}>
              Close assessment
            </Button>
          </>
        )}
        {editable && (
          <Button onClick={handlePublish} disabled={publishing}>
            {publishing ? "Publishing..." : "Publish"}
          </Button>
        )}
      </div>

      {publishErrors && (
        <Card className="mt-4 border-red-300">
          <CardContent className="py-4">
            <p className="mb-2 text-sm font-medium text-red-600">Cannot publish yet:</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-red-600">
              {publishErrors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-lg font-medium">Questions</h2>
        {editable && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Add Question"}</Button>}
      </div>

      {showForm && (
        <Card className="mt-4 max-w-xl">
          <CardHeader>
            <CardTitle className="text-base">New question</CardTitle>
          </CardHeader>
          <CardContent>
            <QuestionForm
              assessmentId={id}
              onAdded={() => {
                setShowForm(false);
                load();
              }}
            />
          </CardContent>
        </Card>
      )}

      <div className="mt-4 space-y-3">
        {questions === null && <Skeleton className="h-20 w-full" />}
        {questions !== null && questions.length === 0 && (
          <p className="text-sm text-muted-foreground">No questions yet.</p>
        )}
        {questions?.map((q, i) => (
          <Card key={q.id}>
            <CardContent className="py-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">
                    Q{i + 1} · {q.question_type} · {q.marks} marks
                  </p>
                  <p className="mt-1 font-medium">{q.question_text}</p>
                  {q.options.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {q.options.map((o) => (
                        <li key={o.id} className={`text-sm ${o.is_correct ? "font-medium text-green-700" : ""}`}>
                          {o.is_correct ? "✓ " : "— "}
                          {o.option_text}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {editable && (
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(q.id)}>
                    Delete
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
