"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LayoutGrid, Users, Sparkles, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { StatCard } from "@/components/stat-card";
import { TrendArrow } from "@/components/trend-arrow";
import {
  getDashboard,
  getStudentPerformance,
  generatePractice,
  type DashboardOverview,
  type StudentPerformance,
  ApiError,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

export default function DashboardOverviewPage() {
  const { user } = useAuth();
  if (!user) return null;
  return user.role === "TEACHER" ? (
    <TeacherOverview name={user.name} />
  ) : (
    <StudentOverview studentId={user.id} name={user.name} />
  );
}

function TeacherOverview({ name }: { name: string }) {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard"));
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader title={`Welcome back, ${name.split(" ")[0]}`} description="A quick look at your batches and students." />

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-4 sm:max-w-md">
        <StatCard label="Total batches" value={data === null ? null : data.total_batches} icon={LayoutGrid} />
        <StatCard label="Total students" value={data === null ? null : data.total_students} icon={Users} />
      </div>
    </div>
  );
}

function StudentOverview({ studentId, name }: { studentId: string; name: string }) {
  const router = useRouter();
  const [perf, setPerf] = useState<StudentPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    getStudentPerformance(studentId)
      .then(setPerf)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load performance"));
  }, [studentId]);

  async function handleGeneratePractice(topicId: string) {
    setGenerateError(null);
    setGeneratingTopicId(topicId);
    try {
      const practiceSet = await generatePractice(studentId, topicId);
      router.push(`/dashboard/practice/${practiceSet.id}`);
    } catch (err) {
      setGenerateError(err instanceof ApiError ? err.message : "Failed to generate practice set");
      setGeneratingTopicId(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title={`Welcome back, ${name.split(" ")[0]}`} description="Here's where your progress stands." />

      {error && <ErrorBanner message={error} />}

      {!error && perf === null && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="border-0 shadow-sm ring-1 ring-border">
              <CardContent className="h-20 animate-pulse rounded-md bg-muted/60" />
            </Card>
          ))}
        </div>
      )}

      {perf !== null && perf.topics.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-muted/20 px-6 py-14 text-center text-sm text-muted-foreground">
          No graded test results yet — your progress will show up here once you&apos;ve completed a test.
        </div>
      )}

      {perf !== null && perf.topics.length > 0 && (
        <>
          <div className="max-w-xs">
            <StatCard label="Overall mastery" value={`${perf.overall_mastery}%`} icon={TrendingUp} />
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Strengths</CardTitle>
              </CardHeader>
              <CardContent>
                {perf.strengths.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No topics above 75% mastery yet.</p>
                ) : (
                  <ul className="space-y-2.5">
                    {perf.strengths.map((t) => (
                      <li key={t.topic_id} className="flex items-center justify-between text-sm">
                        <span className="text-foreground">{t.topic_name}</span>
                        <span className="font-medium text-primary">{t.mastery_score}%</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Needs practice</CardTitle>
              </CardHeader>
              <CardContent>
                {generateError && (
                  <div className="mb-3">
                    <ErrorBanner message={generateError} />
                  </div>
                )}
                {perf.weak_topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No weak topics right now.</p>
                ) : (
                  <ul className="space-y-3">
                    {perf.weak_topics.map((t) => (
                      <li key={t.topic_id} className="flex items-center justify-between gap-3 text-sm">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate text-foreground">{t.topic_name}</span>
                          <span className="shrink-0 font-medium text-destructive">{t.mastery_score}%</span>
                          <TrendArrow trend={t.trend} />
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          className="shrink-0 gap-1.5"
                          disabled={generatingTopicId === t.topic_id}
                          onClick={() => handleGeneratePractice(t.topic_id)}
                        >
                          <Sparkles className="size-3.5" />
                          {generatingTopicId === t.topic_id ? "Generating..." : "Generate practice"}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground">
            <Link href="/dashboard/assessments" className="font-medium text-primary underline-offset-4 hover:underline">
              View your tests
            </Link>{" "}
            for details. Mastery is a product-defined estimate, not a certified measurement of ability.
          </p>
        </>
      )}
    </div>
  );
}
