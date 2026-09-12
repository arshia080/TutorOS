"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { listBatches, createBatch, type Batch, ApiError } from "@/lib/api";

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [grade, setGrade] = useState("");
  const [section, setSection] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function load() {
    setError(null);
    listBatches()
      .then(setBatches)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load batches"));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createBatch({ name, grade: grade || undefined, section: section || undefined });
      setName("");
      setGrade("");
      setSection("");
      setShowForm(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create batch");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Batches</h1>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Batch"}</Button>
      </div>

      {showForm && (
        <Card className="mt-4 max-w-md">
          <CardHeader>
            <CardTitle className="text-base">Create batch</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="name">Name</Label>
                <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="grade">Grade</Label>
                  <Input id="grade" value={grade} onChange={(e) => setGrade(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="section">Section</Label>
                  <Input id="section" value={section} onChange={(e) => setSection(e.target.value)} />
                </div>
              </div>
              {formError && <p className="text-sm text-red-600">{formError}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating..." : "Create"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="mt-6">
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!error && batches === null && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {batches !== null && batches.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">
            No batches yet. Create your first one to start adding students.
          </p>
        )}

        {batches !== null && batches.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Grade</TableHead>
                <TableHead>Section</TableHead>
                <TableHead>Students</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batches.map((batch) => (
                <TableRow key={batch.id}>
                  <TableCell>
                    <Link href={`/dashboard/batches/${batch.id}`} className="font-medium underline">
                      {batch.name}
                    </Link>
                  </TableCell>
                  <TableCell>{batch.grade ?? "—"}</TableCell>
                  <TableCell>{batch.section ?? "—"}</TableCell>
                  <TableCell>{batch.student_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
