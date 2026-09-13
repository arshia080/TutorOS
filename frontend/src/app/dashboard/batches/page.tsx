"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutGrid, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
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
    <div className="space-y-6">
      <PageHeader
        title="Batches"
        description="Groups of students you teach together."
        icon={LayoutGrid}
        action={
          <Button className="gap-1.5" onClick={() => setShowForm((v) => !v)}>
            {!showForm && <Plus className="size-4" />}
            {showForm ? "Cancel" : "New batch"}
          </Button>
        }
      />

      {showForm && (
        <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
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
              {formError && <ErrorBanner message={formError} />}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating..." : "Create"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {error && <ErrorBanner message={error} />}

      {!error && batches === null && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )}

      {batches !== null && batches.length === 0 && !error && (
        <EmptyState
          icon={LayoutGrid}
          title="No batches yet"
          description="Create your first batch to start adding students."
          action={<Button onClick={() => setShowForm(true)}>New batch</Button>}
        />
      )}

      {batches !== null && batches.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
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
                    <Link
                      href={`/dashboard/batches/${batch.id}`}
                      className="font-medium text-foreground hover:text-primary"
                    >
                      {batch.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{batch.grade ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{batch.section ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{batch.student_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
