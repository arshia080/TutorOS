"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ClipboardCheck, Sparkles, Upload, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
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
import { AIGenerateForm } from "./ai-generate-form";
import { PDFUploadForm } from "./pdf-upload-form";

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
  const [showAIForm, setShowAIForm] = useState(false);
  const [showPdfForm, setShowPdfForm] = useState(false);
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
    <div className="space-y-6">
      <PageHeader
        title="Assessments"
        description="Build, generate, and publish tests for your batches."
        icon={ClipboardCheck}
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              className="gap-1.5"
              onClick={() => {
                setShowPdfForm((v) => !v);
                setShowAIForm(false);
                setShowForm(false);
              }}
            >
              <Upload className="size-4" />
              {showPdfForm ? "Cancel" : "Upload PDF"}
            </Button>
            <Button
              variant="outline"
              className="gap-1.5"
              onClick={() => {
                setShowAIForm((v) => !v);
                setShowPdfForm(false);
                setShowForm(false);
              }}
            >
              <Sparkles className="size-4" />
              {showAIForm ? "Cancel" : "Generate with AI"}
            </Button>
            <Button
              className="gap-1.5"
              onClick={() => {
                setShowForm((v) => !v);
                setShowAIForm(false);
                setShowPdfForm(false);
              }}
            >
              {!showForm && <Plus className="size-4" />}
              {showForm ? "Cancel" : "New assessment"}
            </Button>
          </div>
        }
      />

      {showAIForm && (
        <Card className="max-w-lg border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4 text-primary" />
              Generate questions with AI
            </CardTitle>
          </CardHeader>
          <CardContent>
            <AIGenerateForm />
          </CardContent>
        </Card>
      )}

      {showPdfForm && (
        <Card className="max-w-lg border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Upload className="size-4 text-primary" />
              Extract questions from a PDF
            </CardTitle>
          </CardHeader>
          <CardContent>
            <PDFUploadForm />
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card className="max-w-lg border-0 shadow-sm ring-1 ring-border">
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
              {formError && <ErrorBanner message={formError} />}
              <Button type="submit" disabled={submitting || !batchId || !subjectId}>
                {submitting ? "Creating..." : "Create and add questions"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {error && <ErrorBanner message={error} />}
        {!error && assessments === null && (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </>
        )}
        {assessments !== null && assessments.length === 0 && !error && (
          <EmptyState icon={ClipboardCheck} title="No assessments yet" />
        )}
        {assessments?.map((a) => (
          <Link key={a.id} href={`/dashboard/assessments/${a.id}`}>
            <Card className="border-0 shadow-sm ring-1 ring-border transition-shadow hover:shadow-md">
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <p className="font-medium text-foreground">{a.title}</p>
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
    <div className="space-y-6">
      <PageHeader title="Tests" description="Assessments assigned to you." icon={ClipboardCheck} />

      <div className="space-y-2">
        {error && <ErrorBanner message={error} />}
        {!error && assessments === null && (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </>
        )}
        {assessments !== null && assessments.length === 0 && !error && (
          <EmptyState icon={ClipboardCheck} title="No tests assigned yet" />
        )}
        {assessments?.map((a) => (
          <Card key={a.id} className="border-0 shadow-sm ring-1 ring-border">
            <CardContent className="flex items-center justify-between py-4">
              <div>
                <p className="font-medium text-foreground">{a.title}</p>
                <p className="text-sm text-muted-foreground">
                  {a.duration_minutes} min · {a.total_marks} marks
                </p>
              </div>
              {a.status === "CLOSED" ? (
                <Button
                  variant="outline"
                  nativeButton={false}
                  render={<Link href={`/dashboard/assessments/${a.id}/attempt`}>View results</Link>}
                />
              ) : (
                <Button
                  nativeButton={false}
                  render={<Link href={`/dashboard/assessments/${a.id}/attempt`}>Start</Link>}
                />
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
