"use client";

import { use, useEffect, useState } from "react";
import { GraduationCap, KeyRound, MessageSquarePlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import {
  getStudent,
  listBatches,
  generateInviteCode,
  createRemark,
  listRemarksForStudent,
  type Student,
  type Batch,
  type TeacherRemark,
  type RemarkCategory,
  type InviteCode,
  ApiError,
} from "@/lib/api";

const CATEGORIES: RemarkCategory[] = ["GENERAL", "ACADEMIC", "BEHAVIOR", "ATTENDANCE"];

export default function StudentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: studentId } = use(params);
  const [student, setStudent] = useState<Student | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [invite, setInvite] = useState<InviteCode | null>(null);
  const [generating, setGenerating] = useState(false);

  const [remarks, setRemarks] = useState<TeacherRemark[] | null>(null);
  const [batchId, setBatchId] = useState("");
  const [remarkText, setRemarkText] = useState("");
  const [category, setCategory] = useState<RemarkCategory>("GENERAL");
  const [visibleToParent, setVisibleToParent] = useState(true);
  const [submittingRemark, setSubmittingRemark] = useState(false);

  useEffect(() => {
    getStudent(studentId)
      .then(setStudent)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load student"));
    listBatches().then(setBatches).catch(() => setBatches([]));
    loadRemarks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId]);

  function loadRemarks() {
    listRemarksForStudent(studentId)
      .then(setRemarks)
      .catch(() => setRemarks([]));
  }

  async function handleGenerateInvite() {
    setGenerating(true);
    try {
      const code = await generateInviteCode(studentId);
      setInvite(code);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate invite code");
    } finally {
      setGenerating(false);
    }
  }

  async function handleAddRemark(e: React.FormEvent) {
    e.preventDefault();
    if (!batchId) return;
    setSubmittingRemark(true);
    try {
      await createRemark(studentId, { batch_id: batchId, remark_text: remarkText, category, visible_to_parent: visibleToParent });
      setRemarkText("");
      loadRemarks();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add remark");
    } finally {
      setSubmittingRemark(false);
    }
  }

  if (error && student === null) return <ErrorBanner message={error} />;

  if (student === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title={student.name} description={student.email} icon={GraduationCap} />

      <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="size-4 text-primary" />
            Parent invite code
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Share this one-time code with a parent -- entering it links them instantly.
          </p>
          {invite && (
            <div className="rounded-lg border border-border bg-muted/40 px-4 py-3">
              <p className="font-mono text-lg font-semibold tracking-widest text-foreground">{invite.code}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Expires {new Date(invite.expires_at).toLocaleString()}
              </p>
            </div>
          )}
          <Button onClick={handleGenerateInvite} disabled={generating}>
            {generating ? "Generating..." : invite ? "Generate new code" : "Generate invite code"}
          </Button>
        </CardContent>
      </Card>

      {error && <ErrorBanner message={error} />}

      <div>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          <MessageSquarePlus className="size-4" />
          Remarks
        </h2>

        <Card className="mb-4 max-w-md border-0 shadow-sm ring-1 ring-border">
          <CardContent className="py-4">
            <form onSubmit={handleAddRemark} className="space-y-3">
              <Select value={batchId || undefined} onValueChange={(v: string | null) => setBatchId(v ?? "")}>
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
              <Textarea
                placeholder="Write a remark..."
                required
                value={remarkText}
                onChange={(e) => setRemarkText(e.target.value)}
              />
              <div className="flex items-center gap-3">
                <Select value={category} onValueChange={(v: string | null) => v && setCategory(v as RemarkCategory)}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={visibleToParent}
                    onChange={(e) => setVisibleToParent(e.target.checked)}
                  />
                  Visible to parent
                </label>
              </div>
              <Button type="submit" disabled={submittingRemark || !batchId}>
                {submittingRemark ? "Adding..." : "Add remark"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {remarks === null && <Skeleton className="h-20 w-full" />}
        {remarks !== null && remarks.length === 0 && (
          <p className="text-sm text-muted-foreground">No remarks yet.</p>
        )}
        {remarks !== null && remarks.length > 0 && (
          <div className="space-y-2">
            {remarks.map((r) => (
              <Card key={r.id} className="border-0 shadow-sm ring-1 ring-border">
                <CardContent className="py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{r.category}</Badge>
                      {!r.visible_to_parent && <Badge variant="outline">Hidden from parent</Badge>}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-foreground">{r.remark_text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
