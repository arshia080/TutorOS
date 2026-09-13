"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { UserPlus, Users, ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import {
  getBatch,
  listBatchStudents,
  addStudentToBatch,
  type Batch,
  type BatchStudentEntry,
  ApiError,
} from "@/lib/api";

export default function BatchDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [students, setStudents] = useState<BatchStudentEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function load() {
    setError(null);
    Promise.all([getBatch(id), listBatchStudents(id)])
      .then(([batchData, studentsData]) => {
        setBatch(batchData);
        setStudents(studentsData);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load batch"));
  }

  useEffect(load, [id]);

  async function handleAddStudent(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await addStudentToBatch(id, { name, email });
      setName("");
      setEmail("");
      setShowForm(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to add student");
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return <ErrorBanner message={error} />;
  }

  if (batch === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={batch.name}
        description={
          [batch.grade && `Grade ${batch.grade}`, batch.section && `Section ${batch.section}`, batch.academic_year]
            .filter(Boolean)
            .join(" · ") || "No details set"
        }
        icon={Users}
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="gap-1.5"
              nativeButton={false}
              render={
                <Link href={`/dashboard/batches/${id}/syllabus`}>
                  <ListChecks className="size-4" />
                  Syllabus
                </Link>
              }
            />
            <Button className="gap-1.5" onClick={() => setShowForm((v) => !v)}>
              {!showForm && <UserPlus className="size-4" />}
              {showForm ? "Cancel" : "Add student"}
            </Button>
          </div>
        }
      />

      {showForm && (
        <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="text-base">Add student</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddStudent} className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="student-name">Name</Label>
                <Input id="student-name" required value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="student-email">Email</Label>
                <Input
                  id="student-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {formError && <ErrorBanner message={formError} />}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Adding..." : "Add"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Roster</h2>

        {students === null && <Skeleton className="h-10 w-full" />}

        {students !== null && students.length === 0 && (
          <EmptyState
            icon={UserPlus}
            title="No students in this batch yet"
            description="Add one to get started."
            action={<Button onClick={() => setShowForm(true)}>Add student</Button>}
          />
        )}

        {students !== null && students.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Joined</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.map((s) => (
                  <TableRow key={s.student_id}>
                    <TableCell className="font-medium">
                      <Link href={`/dashboard/students/${s.student_id}`} className="hover:text-primary">
                        {s.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{s.email}</TableCell>
                    <TableCell>
                      <Badge variant={s.status === "ACTIVE" ? "default" : "secondary"}>{s.status}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(s.joined_at).toLocaleDateString()}
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
