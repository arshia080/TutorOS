"use client";

import { use, useEffect, useState } from "react";
import { ClipboardList } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import {
  getHomework,
  listSubmissionRoster,
  downloadAttachment,
  downloadSubmission,
  updateHomework,
  type Homework,
  type RosterEntry,
  ApiError,
} from "@/lib/api";

export default function HomeworkDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [homework, setHomework] = useState<Homework | null>(null);
  const [roster, setRoster] = useState<RosterEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reopening, setReopening] = useState(false);

  function load() {
    setError(null);
    Promise.all([getHomework(id), listSubmissionRoster(id)])
      .then(([hw, r]) => {
        setHomework(hw);
        setRoster(r);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load homework"));
  }

  useEffect(load, [id]);

  async function handleReopen() {
    setReopening(true);
    try {
      await updateHomework(id, { allow_late_submissions: true });
      load();
    } finally {
      setReopening(false);
    }
  }

  if (error) return <ErrorBanner message={error} />;

  if (homework === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const overdue = new Date(homework.due_date).getTime() < Date.now();

  return (
    <div className="space-y-6">
      <PageHeader
        title={homework.title}
        description={homework.description || undefined}
        icon={ClipboardList}
      />

      <div className="-mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <span>
          Due {new Date(homework.due_date).toLocaleString()}
          {homework.allow_late_submissions && " · late submissions allowed"}
        </span>
        {homework.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {homework.attachments.map((a) => (
              <Button key={a.id} variant="outline" size="sm" onClick={() => downloadAttachment(homework.id, a)}>
                {a.file_name}
              </Button>
            ))}
          </div>
        )}
      </div>

      {overdue && !homework.allow_late_submissions && (
        <Button variant="outline" onClick={handleReopen} disabled={reopening}>
          {reopening ? "Reopening..." : "Reopen for late submissions"}
        </Button>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Submissions</h2>
        {roster === null && <Skeleton className="h-10 w-full" />}
        {roster !== null && roster.length === 0 && (
          <EmptyState icon={ClipboardList} title="No students in this batch" />
        )}
        {roster !== null && roster.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Student</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {roster.map((r) => (
                  <TableRow key={r.student_id}>
                    <TableCell>
                      <p className="font-medium">{r.name}</p>
                      <p className="text-xs text-muted-foreground">{r.email}</p>
                    </TableCell>
                    <TableCell>
                      {r.status === null && <Badge variant="secondary">Pending</Badge>}
                      {r.status === "SUBMITTED" && <Badge variant="default">Submitted</Badge>}
                      {r.status === "LATE" && <Badge variant="destructive">Late</Badge>}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell>
                      {r.status !== null && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => downloadSubmission(homework.id, r.student_id, `${r.name}-submission`)}
                        >
                          Download
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
