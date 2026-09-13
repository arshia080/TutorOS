"use client";

import { use, useEffect, useState } from "react";
import { GraduationCap, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { StatCard } from "@/components/stat-card";
import { TrendArrow } from "@/components/trend-arrow";
import { getChildProgress, type ChildProgress, ApiError } from "@/lib/api";

export default function ChildProgressPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [progress, setProgress] = useState<ChildProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getChildProgress(id)
      .then(setProgress)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load progress"));
  }, [id]);

  if (error) return <ErrorBanner message={error} />;

  if (progress === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const { performance } = progress;

  return (
    <div className="space-y-8">
      <PageHeader title={progress.student_name} description="Mastery, syllabus progress, tests, and teacher remarks." icon={GraduationCap} />

      <div className="max-w-xs">
        <StatCard label="Overall mastery" value={`${performance.overall_mastery}%`} />
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <Card className="border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="text-base">Topic mastery</CardTitle>
          </CardHeader>
          <CardContent>
            {performance.topics.length === 0 ? (
              <p className="text-sm text-muted-foreground">No graded test results yet.</p>
            ) : (
              <ul className="space-y-2.5">
                {performance.topics.map((t) => (
                  <li key={t.topic_id} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-foreground">
                      {t.topic_name}
                      <TrendArrow trend={t.trend} />
                    </span>
                    <span
                      className={`font-medium ${t.mastery_score < 60 ? "text-destructive" : "text-primary"}`}
                    >
                      {t.mastery_score}% · {t.mastery_category}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="text-base">Syllabus completion</CardTitle>
          </CardHeader>
          <CardContent>
            {progress.syllabus.length === 0 ? (
              <p className="text-sm text-muted-foreground">No syllabus tracking recorded yet.</p>
            ) : (
              <div className="space-y-4">
                {progress.syllabus.map((s) => (
                  <div key={s.subject_id} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-foreground">{s.subject_name}</span>
                      <span className="font-medium text-foreground">
                        {s.completed_topics}/{s.total_topics} · {s.percentage}%
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${s.percentage}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Recent tests</h2>
        {progress.recent_tests.length === 0 ? (
          <p className="text-sm text-muted-foreground">No test results yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Assessment</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Submitted</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {progress.recent_tests.map((t) => (
                  <TableRow key={t.assessment_id}>
                    <TableCell className="font-medium">{t.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {t.score ?? "—"} / {t.total_marks}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {t.submitted_at ? new Date(t.submitted_at).toLocaleDateString() : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <MessageSquare className="size-4 text-primary" />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Teacher remarks</h2>
        </div>
        {progress.remarks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No remarks yet.</p>
        ) : (
          <div className="space-y-2">
            {progress.remarks.map((r) => (
              <Card key={r.id} className="border-0 shadow-sm ring-1 ring-border">
                <CardContent className="py-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary">{r.category}</Badge>
                    <span className="text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="mt-2 text-sm text-foreground">{r.remark_text}</p>
                  <p className="mt-1 text-xs text-muted-foreground">— {r.teacher_name}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        Mastery is a product-defined estimate, not a certified measurement of ability.
      </p>
    </div>
  );
}
