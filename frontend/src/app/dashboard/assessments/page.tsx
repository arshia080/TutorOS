"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/use-auth";
import {
  listAssessments,
  createAssessment,
  listBatches,
  listSubjects,
  type Assessment,
  type Batch,
  type Subject,
  ApiError,
} from "@/lib/api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  DRAFT: "secondary",
  REVIEW: "outline",
  PUBLISHED: "default",
  CLOSED: "destructive",
};

export default function AssessmentsPage() {
  const { user } = useAuth();
  if (!user) return null;
  return user.role === "TEACHER" ? <TeacherAssessmentsView /> : <StudentAssessmentsView />;
}

function TeacherAssessmentsView() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<Assessment[] | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [batchId, setBatchId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("30");
  const [totalMarks, setTotalMarks] = useState("10");

  function load() {
    setError(null);
    listAssessments()
      .then(setAssessments)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load assessments"));
  }

  useEffect(load, []);
  useEffect(() => {
    listBatches().then(setBatches).catch(() => setBatches([]));
    listSubjects().then(setSubjects).catch(() => setSubjects([]));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const assessment = await createAssessment({
        batch_id: batchId,
        subject_id: subjectId,
        title,
        duration_minutes: Number(duration),
        total_marks: Number(totalMarks),
      });
      router.push(`/dashboard/assessments/${assessment.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create assessment");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Assessments</h1>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Assessment"}</Button>
      </div>

      {showForm && (
        <Card className="mt-4 max-w-lg">
          <CardHeader>
            <CardTitle className="text-base">Create assessment</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Batch</Label>
                  <Select onValueChange={(v: string | null) => setBatchId(v ?? "")}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select batch" />
                    </SelectTrigger>
                    <SelectContent>
                      {batches.map((b) => (
                        <SelectItem key={b.id} value={b.id}>
                          {b.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Subject</Label>
                  <Select onValueChange={(v: string | null) => setSubjectId(v ?? "")}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select subject" />
                    </SelectTrigger>
                    <SelectContent>
                      {subjects.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="title">Title</Label>
                <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="duration">Duration (minutes)</Label>
                  <Input
                    id="duration"
                    type="number"
                    min={1}
                    required
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="total_marks">Total marks</Label>
                  <Input
                    id="total_marks"
                    type="number"
                    min={1}
                    required
                    value={totalMarks}
                    onChange={(e) => setTotalMarks(e.target.value)}
                  />
                </div>
              </div>
              {formError && <p className="text-sm text-red-600">{formError}</p>}
              <Button type="submit" disabled={submitting || !batchId || !subjectId}>
                {submitting ? "Creating..." : "Create and add questions"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="mt-6 space-y-2">
        {error && <p className="text-sm text-red-600">{error}</p>}
        {!error && assessments === null && (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </>
        )}
        {assessments !== null && assessments.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">No assessments yet.</p>
        )}
        {assessments?.map((a) => (
          <Link key={a.id} href={`/dashboard/assessments/${a.id}`}>
            <Card className="transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <p className="font-medium">{a.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {a.duration_minutes} min · {a.total_marks} marks
                  </p>
                </div>
                <Badge variant={STATUS_VARIANT[a.status]}>{a.status}</Badge>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StudentAssessmentsView() {
  const [assessments, setAssessments] = useState<Assessment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAssessments()
      .then(setAssessments)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load assessments"));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Tests</h1>

      <div className="mt-6 space-y-2">
        {error && <p className="text-sm text-red-600">{error}</p>}
        {!error && assessments === null && (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </>
        )}
        {assessments !== null && assessments.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">No tests assigned yet.</p>
        )}
        {assessments?.map((a) => (
          <Card key={a.id}>
            <CardContent className="flex items-center justify-between py-4">
              <div>
                <p className="font-medium">{a.title}</p>
                <p className="text-sm text-muted-foreground">
                  {a.duration_minutes} min · {a.total_marks} marks
                </p>
              </div>
              {a.status === "CLOSED" ? (
                <Link href={`/dashboard/assessments/${a.id}/attempt`}>
                  <Button variant="outline">View results</Button>
                </Link>
              ) : (
                <Link href={`/dashboard/assessments/${a.id}/attempt`}>
                  <Button>Start</Button>
                </Link>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
