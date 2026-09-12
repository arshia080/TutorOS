"use client";

import { use, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
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
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (batch === null) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">{batch.name}</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {[batch.grade && `Grade ${batch.grade}`, batch.section && `Section ${batch.section}`, batch.academic_year]
          .filter(Boolean)
          .join(" · ") || "No details set"}
      </p>

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-lg font-medium">Roster</h2>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Add Student"}</Button>
      </div>

      {showForm && (
        <Card className="mt-4 max-w-md">
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
              {formError && <p className="text-sm text-red-600">{formError}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Adding..." : "Add"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="mt-4">
        {students === null && <Skeleton className="h-10 w-full" />}

        {students !== null && students.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No students in this batch yet. Add one to get started.
          </p>
        )}

        {students !== null && students.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Joined</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((s) => (
                <TableRow key={s.student_id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell>{s.email}</TableCell>
                  <TableCell>
                    <Badge variant={s.status === "ACTIVE" ? "default" : "secondary"}>{s.status}</Badge>
                  </TableCell>
                  <TableCell>{new Date(s.joined_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
