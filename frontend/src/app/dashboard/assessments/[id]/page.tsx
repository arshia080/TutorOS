"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
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

      {actionError && <p className="mt-2 text-sm text-red-600">{actionError}</p>}

      <div className="mt-4 space-y-3">
        {questions === null && <Skeleton className="h-20 w-full" />}
        {questions !== null && questions.length === 0 && (
          <p className="text-sm text-muted-foreground">No questions yet.</p>
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
            <Card key={q.id}>
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span>
                        Q{i + 1} · {q.question_type} · {q.marks} marks
                        {q.topic_id && ` · ${topics.find((t) => t.id === q.topic_id)?.name ?? "topic set"}`}
                        {q.difficulty && ` · ${q.difficulty}`}
                      </span>
                      {q.source !== "MANUAL" && <Badge variant="secondary">{SOURCE_LABEL[q.source] ?? q.source}</Badge>}
                    </div>
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
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditingId(q.id)}>
                        Edit
                      </Button>
                      {q.source !== "MANUAL" && (
                        <Button variant="ghost" size="sm" disabled={regeneratingId === q.id} onClick={() => handleRegenerate(q.id)}>
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
    <Card className="border-primary">
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
        {error && <p className="text-sm text-red-600">{error}</p>}
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
