"use client";

import { Fragment, use, useEffect, useState } from "react";
import { ClipboardList } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import {
  listAttempts,
  listStudents,
  reviewAttempt,
  gradeResponse,
  type Attempt,
  type AttemptReview,
  type Student,
  ApiError,
} from "@/lib/api";

export default function AttemptsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: assessmentId } = use(params);
  const [attempts, setAttempts] = useState<Attempt[] | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  function load() {
    setError(null);
    listAttempts(assessmentId)
      .then(setAttempts)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load attempts"));
    listStudents().then(setStudents).catch(() => setStudents([]));
  }

  useEffect(load, [assessmentId]);

  const studentById = Object.fromEntries(students.map((s) => [s.id, s]));

  return (
    <div className="space-y-6">
      <PageHeader title="Attempts" description="Review and grade student attempts." icon={ClipboardList} />

      {error && <ErrorBanner message={error} />}
      {!error && attempts === null && <Skeleton className="h-10 w-full" />}
      {attempts !== null && attempts.length === 0 && (
        <EmptyState icon={ClipboardList} title="No students have started this test yet" />
      )}
      {attempts !== null && attempts.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Student</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Score</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {attempts.map((a) => {
                const student = studentById[a.student_id];
                return (
                  <Fragment key={a.id}>
                    <TableRow>
                      <TableCell className="font-medium">
                        {student ? `${student.name} (${student.email})` : a.student_id}
                      </TableCell>
                      <TableCell>
                        <Badge variant={a.status === "IN_PROGRESS" ? "secondary" : "default"}>{a.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{a.total_score ?? "—"}</TableCell>
                      <TableCell>
                        {a.status !== "IN_PROGRESS" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                          >
                            {expanded === a.id ? "Hide" : "Review / Grade"}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                    {expanded === a.id && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={4} className="bg-muted/20">
                          <GradingPanel assessmentId={assessmentId} attemptId={a.id} onGraded={load} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function GradingPanel({
  assessmentId,
  attemptId,
  onGraded,
}: {
  assessmentId: string;
  attemptId: string;
  onGraded: () => void;
}) {
  const [review, setReview] = useState<AttemptReview | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  function load() {
    reviewAttempt(attemptId).then(setReview);
  }

  useEffect(load, [attemptId]);

  if (!review) return <Skeleton className="h-20 w-full" />;

  const questionById = Object.fromEntries(review.questions.map((q) => [q.id, q]));

  async function handleGrade(questionId: string) {
    setSaving(questionId);
    try {
      await gradeResponse(assessmentId, attemptId, questionId, Number(drafts[questionId] ?? 0));
      load();
      onGraded();
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-2 py-2">
      {review.responses.map((r) => {
        const q = questionById[r.question_id];
        if (!q) return null;
        const needsGrading = q.options.length === 0 && r.score === null;
        return (
          <Card key={r.question_id} className="border-0 shadow-sm ring-1 ring-border">
            <CardContent className="py-3">
              <p className="text-sm font-medium text-foreground">{q.question_text}</p>
              {q.options.length > 0 ? (
                <p className="mt-1 text-sm text-muted-foreground">
                  {r.is_correct ? "Correct" : "Incorrect"} · Score: {r.score} / {q.marks}
                </p>
              ) : (
                <>
                  <p className="mt-1 text-sm text-muted-foreground">Answer: {r.response_text || "(no answer)"}</p>
                  {needsGrading ? (
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={q.marks}
                        step="0.5"
                        className="w-24"
                        placeholder="Score"
                        value={drafts[q.id] ?? ""}
                        onChange={(e) => setDrafts((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      />
                      <span className="text-sm text-muted-foreground">/ {q.marks}</span>
                      <Button size="sm" disabled={saving === q.id} onClick={() => handleGrade(q.id)}>
                        Save score
                      </Button>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm font-medium text-primary">
                      Graded: {r.score} / {q.marks}
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
