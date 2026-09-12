"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/use-auth";
import { dueCountdown } from "@/lib/format";
import {
  listHomework,
  listSubmissionRoster,
  getMySubmission,
  submitHomework,
  downloadAttachment,
  type Homework,
  type Submission,
  ApiError,
} from "@/lib/api";
import { HomeworkForm } from "./homework-form";

interface Counts {
  submitted: number;
  late: number;
  pending: number;
}

export default function HomeworkPage() {
  const { user } = useAuth();

  if (!user) return null;
  return user.role === "TEACHER" ? <TeacherHomeworkView /> : <StudentHomeworkView />;
}

function TeacherHomeworkView() {
  const [homework, setHomework] = useState<Homework[] | null>(null);
  const [counts, setCounts] = useState<Record<string, Counts>>({});
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  function load() {
    setError(null);
    listHomework()
      .then(async (items) => {
        setHomework(items);
        const entries = await Promise.all(
          items.map(async (hw) => {
            try {
              const roster = await listSubmissionRoster(hw.id);
              const submitted = roster.filter((r) => r.status === "SUBMITTED").length;
              const late = roster.filter((r) => r.status === "LATE").length;
              const pending = roster.filter((r) => r.status === null).length;
              return [hw.id, { submitted, late, pending }] as const;
            } catch {
              return [hw.id, { submitted: 0, late: 0, pending: 0 }] as const;
            }
          }),
        );
        setCounts(Object.fromEntries(entries));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load homework"));
  }

  useEffect(load, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Homework</h1>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Homework"}</Button>
      </div>

      {showForm && (
        <Card className="mt-4 max-w-lg">
          <CardHeader>
            <CardTitle className="text-base">Create homework</CardTitle>
          </CardHeader>
          <CardContent>
            <HomeworkForm
              onCreated={() => {
                setShowForm(false);
                load();
              }}
            />
          </CardContent>
        </Card>
      )}

      <div className="mt-6 space-y-3">
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!error && homework === null && (
          <>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </>
        )}

        {homework !== null && homework.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">No homework assigned yet.</p>
        )}

        {homework?.map((hw) => {
          const c = counts[hw.id];
          const { label, overdue } = dueCountdown(hw.due_date);
          return (
            <Link key={hw.id} href={`/dashboard/homework/${hw.id}`}>
              <Card className="transition-colors hover:bg-muted/50">
                <CardContent className="flex items-center justify-between py-4">
                  <div>
                    <p className="font-medium">{hw.title}</p>
                    <p className="text-sm text-muted-foreground">
                      Due {new Date(hw.due_date).toLocaleString()} ·{" "}
                      <span className={overdue ? "text-red-600" : ""}>{label}</span>
                    </p>
                  </div>
                  {c && (
                    <div className="flex gap-2">
                      <Badge variant="default">{c.submitted} submitted</Badge>
                      {c.late > 0 && <Badge variant="destructive">{c.late} late</Badge>}
                      <Badge variant="secondary">{c.pending} pending</Badge>
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function StudentHomeworkView() {
  const [homework, setHomework] = useState<Homework[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submissions, setSubmissions] = useState<Record<string, Submission | null>>({});
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<Record<string, string>>({});

  function load() {
    setError(null);
    listHomework()
      .then(async (items) => {
        setHomework(items);
        const entries = await Promise.all(
          items.map(async (hw) => {
            try {
              const submission = await getMySubmission(hw.id);
              return [hw.id, submission] as const;
            } catch {
              return [hw.id, null] as const;
            }
          }),
        );
        setSubmissions(Object.fromEntries(entries));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load homework"));
  }

  useEffect(load, []);

  async function handleUpload(homeworkId: string, file: File) {
    setUploading(homeworkId);
    setUploadError((prev) => ({ ...prev, [homeworkId]: "" }));
    try {
      const submission = await submitHomework(homeworkId, file);
      setSubmissions((prev) => ({ ...prev, [homeworkId]: submission }));
    } catch (err) {
      setUploadError((prev) => ({
        ...prev,
        [homeworkId]: err instanceof ApiError ? err.message : "Upload failed",
      }));
    } finally {
      setUploading(null);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">Homework</h1>

      <div className="mt-6 space-y-3">
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!error && homework === null && (
          <>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </>
        )}

        {homework !== null && homework.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">No homework assigned yet.</p>
        )}

        {homework?.map((hw) => {
          const submission = submissions[hw.id];
          const { label, overdue } = dueCountdown(hw.due_date);
          const canSubmit = !overdue || hw.allow_late_submissions;

          return (
            <Card key={hw.id}>
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{hw.title}</p>
                    {hw.description && <p className="text-sm text-muted-foreground">{hw.description}</p>}
                    <p className="mt-1 text-sm text-muted-foreground">
                      Due {new Date(hw.due_date).toLocaleString()} ·{" "}
                      <span className={overdue ? "text-red-600" : ""}>{label}</span>
                    </p>
                    {hw.attachments.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {hw.attachments.map((a) => (
                          <Button
                            key={a.id}
                            variant="outline"
                            size="sm"
                            onClick={() => downloadAttachment(hw.id, a)}
                          >
                            {a.file_name}
                          </Button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    {submission ? (
                      <Badge variant={submission.status === "LATE" ? "destructive" : "default"}>
                        {submission.status === "LATE" ? "Submitted late" : "Submitted"}
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Pending</Badge>
                    )}
                  </div>
                </div>

                <div className="mt-3">
                  {canSubmit ? (
                    <label className="text-sm">
                      <span className="mr-2 text-muted-foreground">
                        {submission ? "Replace submission:" : "Upload submission:"}
                      </span>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                        disabled={uploading === hw.id}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleUpload(hw.id, file);
                        }}
                      />
                    </label>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      The deadline has passed and late submissions aren&apos;t accepted.
                    </p>
                  )}
                  {uploadError[hw.id] && <p className="text-sm text-red-600">{uploadError[hw.id]}</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
