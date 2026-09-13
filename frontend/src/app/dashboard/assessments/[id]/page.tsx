"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardCheck, Eye, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import {
  getAssessment,
  listQuestions,
  deleteQuestion,
  updateQuestion,
  regenerateQuestion,
  publishAssessment,
  closeAssessment,
  listTopics,
  type Assessment,
  type Question,
  type Topic,
  ApiError,
} from "@/lib/api";
import { QuestionForm } from "./question-form";

const SOURCE_LABEL: Record<string, string> = {
  MANUAL: "Manual",
  AI_GENERATED: "AI generated",
  AI_EXTRACTED: "AI extracted",
};

export default function AssessmentBuilderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [publishErrors, setPublishErrors] = useState<string[] | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([getAssessment(id), listQuestions(id)])
      .then(([a, qs]) => {
        setAssessment(a);
        setQuestions(qs);
        listTopics(a.subject_id).then(setTopics).catch(() => setTopics([]));
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

  async function handleRegenerate(questionId: string) {
    setActionError(null);
    setRegeneratingId(questionId);
    try {
      await regenerateQuestion(id, questionId);
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to regenerate question");
    } finally {
      setRegeneratingId(null);
    }
  }

  if (error) return <ErrorBanner message={error} />;

  if (assessment === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={assessment.title}
        description={`${assessment.duration_minutes} min · ${assessment.total_marks} marks declared · ${questionMarksTotal} marks from questions so far`}
        icon={ClipboardCheck}
        action={<Badge className="text-xs">{assessment.status}</Badge>}
      />

      <div className="flex flex-wrap gap-2">
        {assessment.status === "PUBLISHED" && (
          <>
            <Button
              variant="outline"
              className="gap-1.5"
              nativeButton={false}
              render={<Link href={`/dashboard/assessments/${id}/attempts`}>
                <Eye className="size-4" />
                View attempts
              </Link>}
            />
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
        <div className="rounded-lg border border-destructive/25 bg-destructive/5 px-4 py-3">
          <p className="mb-1.5 text-sm font-medium text-destructive">Cannot publish yet:</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-destructive">
            {publishErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Questions</h2>
          {editable && (
            <Button size="sm" className="gap-1.5" onClick={() => setShowForm((v) => !v)}>
              {!showForm && <Plus className="size-3.5" />}
              {showForm ? "Cancel" : "Add question"}
            </Button>
          )}
        </div>

        {showForm && (
          <Card className="mb-4 max-w-xl border-0 shadow-sm ring-1 ring-border">
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

        {actionError && (
          <div className="mb-3">
            <ErrorBanner message={actionError} />
          </div>
        )}

        <div className="space-y-3">
          {questions === null && <Skeleton className="h-20 w-full" />}
          {questions !== null && questions.length === 0 && (
            <EmptyState icon={ClipboardCheck} title="No questions yet" />
          )}
          {questions?.map((q, i) =>
            editingId === q.id ? (
              <EditQuestionCard
                key={q.id}
                assessmentId={id}
                question={q}
                topics={topics}
                onDone={() => {
                  setEditingId(null);
                  load();
                }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <Card key={q.id} className="border-0 shadow-sm ring-1 ring-border">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <span>
                          Q{i + 1} · {q.question_type} · {q.marks} marks
                          {q.topic_id && ` · ${topics.find((t) => t.id === q.topic_id)?.name ?? "topic set"}`}
                          {q.difficulty && ` · ${q.difficulty}`}
                        </span>
                        {q.source !== "MANUAL" && (
                          <Badge variant="secondary">{SOURCE_LABEL[q.source] ?? q.source}</Badge>
                        )}
                      </div>
                      <p className="mt-1 font-medium text-foreground">{q.question_text}</p>
                      {q.options.length > 0 && (
                        <ul className="mt-2 space-y-1">
                          {q.options.map((o) => (
                            <li
                              key={o.id}
                              className={`text-sm ${o.is_correct ? "font-medium text-primary" : "text-muted-foreground"}`}
                            >
                              {o.is_correct ? "✓ " : "— "}
                              {o.option_text}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    {editable && (
                      <div className="flex shrink-0 gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setEditingId(q.id)}>
                          Edit
                        </Button>
                        {q.source !== "MANUAL" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={regeneratingId === q.id}
                            onClick={() => handleRegenerate(q.id)}
                          >
                            {regeneratingId === q.id ? "Regenerating..." : "Regenerate"}
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(q.id)}>
                          Delete
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ),
          )}
        </div>
      </div>
    </div>
  );
}

function EditQuestionCard({
  assessmentId,
  question,
  topics,
  onDone,
  onCancel,
}: {
  assessmentId: string;
  question: Question;
  topics: Topic[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(question.question_text);
  const [topicId, setTopicId] = useState(question.topic_id ?? "");
  const [difficulty, setDifficulty] = useState(question.difficulty ?? "");
  const [marks, setMarks] = useState(String(question.marks));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setError(null);
    setSubmitting(true);
    try {
      await updateQuestion(assessmentId, question.id, {
        question_text: text,
        topic_id: topicId || undefined,
        difficulty: difficulty || undefined,
        marks: Number(marks),
      });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save changes");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="border-0 shadow-sm ring-2 ring-primary">
      <CardContent className="space-y-3 py-4">
        <div className="space-y-1">
          <Label>Question text</Label>
          <Input value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label>Topic</Label>
            <Select value={topicId || undefined} onValueChange={(v: string | null) => setTopicId(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                {topics.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Difficulty</Label>
            <Select value={difficulty || undefined} onValueChange={(v: string | null) => setDifficulty(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="EASY">Easy</SelectItem>
                <SelectItem value="MEDIUM">Medium</SelectItem>
                <SelectItem value="HARD">Hard</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Marks</Label>
            <Input type="number" min={0.5} step="0.5" value={marks} onChange={(e) => setMarks(e.target.value)} />
          </div>
        </div>
        {error && <ErrorBanner message={error} />}
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving..." : "Save"}
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
