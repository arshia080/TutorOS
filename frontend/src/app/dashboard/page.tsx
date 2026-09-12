"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendArrow } from "@/components/trend-arrow";
import {
  getDashboard,
  getStudentPerformance,
  type DashboardOverview,
  type StudentPerformance,
  ApiError,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

export default function DashboardOverviewPage() {
  const { user } = useAuth();
  if (!user) return null;
  return user.role === "TEACHER" ? <TeacherOverview /> : <StudentOverview studentId={user.id} />;
}

function TeacherOverview() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard"));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Overview</h1>
      <p className="mt-1 text-sm text-muted-foreground">A quick look at your batches and students.</p>

      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}

      <div className="mt-6 grid grid-cols-2 gap-4 sm:max-w-md">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Batches</CardTitle>
          </CardHeader>
          <CardContent>
            {data === null ? <Skeleton className="h-8 w-12" /> : <p className="text-3xl font-semibold">{data.total_batches}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Students</CardTitle>
          </CardHeader>
          <CardContent>
            {data === null ? <Skeleton className="h-8 w-12" /> : <p className="text-3xl font-semibold">{data.total_students}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StudentOverview({ studentId }: { studentId: string }) {
  const [perf, setPerf] = useState<StudentPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStudentPerformance(studentId)
      .then(setPerf)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load performance"));
  }, [studentId]);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Your Progress</h1>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {!error && perf === null && (
        <div className="mt-6 space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {perf !== null && perf.topics.length === 0 && (
        <p className="mt-6 text-sm text-muted-foreground">
          No graded test results yet -- your progress will show up here once you've completed a test.
        </p>
      )}

      {perf !== null && perf.topics.length > 0 && (
        <>
          <Card className="mt-6 max-w-xs">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Overall Mastery</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold">{perf.overall_mastery}%</p>
            </CardContent>
          </Card>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Strengths</CardTitle>
              </CardHeader>
              <CardContent>
                {perf.strengths.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No topics above 75% mastery yet.</p>
                ) : (
                  <ul className="space-y-1">
                    {perf.strengths.map((t) => (
                      <li key={t.topic_id} className="flex justify-between text-sm">
                        <span>{t.topic_name}</span>
                        <span className="font-medium text-green-700">{t.mastery_score}%</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Needs Practice</CardTitle>
              </CardHeader>
              <CardContent>
                {perf.weak_topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No weak topics right now.</p>
                ) : (
                  <ul className="space-y-1">
                    {perf.weak_topics.map((t) => (
                      <li key={t.topic_id} className="flex items-center justify-between text-sm">
                        <span>{t.topic_name}</span>
                        <span className="flex items-center gap-2">
                          <span className="font-medium text-red-600">{t.mastery_score}%</span>
                          <TrendArrow trend={t.trend} />
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            <Link href="/dashboard/assessments" className="underline">
              View your tests
            </Link>{" "}
            for details. Mastery is a product-defined estimate, not a certified measurement of ability.
          </p>
        </>
      )}
    </div>
  );
}
