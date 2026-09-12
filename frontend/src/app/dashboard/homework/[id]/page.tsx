"use client";

import { use, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  if (error) return <p className="text-sm text-red-600">{error}</p>;

  if (homework === null) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const overdue = new Date(homework.due_date).getTime() < Date.now();

  return (
    <div>
      <h1 className="text-2xl font-semibold">{homework.title}</h1>
      {homework.description && <p className="mt-1 text-sm text-muted-foreground">{homework.description}</p>}
      <p className="mt-1 text-sm text-muted-foreground">
        Due {new Date(homework.due_date).toLocaleString()}
        {homework.allow_late_submissions && " · late submissions allowed"}
      </p>

      {homework.attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {homework.attachments.map((a) => (
            <Button key={a.id} variant="outline" size="sm" onClick={() => downloadAttachment(homework.id, a)}>
              {a.file_name}
            </Button>
          ))}
        </div>
      )}

      {overdue && !homework.allow_late_submissions && (
        <Button className="mt-4" variant="outline" onClick={handleReopen} disabled={reopening}>
          {reopening ? "Reopening..." : "Reopen for late submissions"}
        </Button>
      )}

      <h2 className="mt-6 text-lg font-medium">Submissions</h2>
      <div className="mt-2">
        {roster === null && <Skeleton className="h-10 w-full" />}
        {roster !== null && roster.length === 0 && (
          <p className="text-sm text-muted-foreground">No students in this batch.</p>
        )}
        {roster !== null && roster.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
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
                  <TableCell>{r.submitted_at ? new Date(r.submitted_at).toLocaleString() : "—"}</TableCell>
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
        )}
      </div>
    </div>
  );
}
