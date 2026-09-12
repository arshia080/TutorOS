"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  uploadPdfForExtraction,
  getExtractionJob,
  listBatches,
  listSubjects,
  type Batch,
  type Subject,
  ApiError,
} from "@/lib/api";

type Stage = "idle" | "uploading" | "processing" | "failed";

export function PDFUploadForm() {
  const router = useRouter();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [batchId, setBatchId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBatches().then(setBatches).catch(() => setBatches([]));
    listSubjects().then(setSubjects).catch(() => setSubjects([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setStage("uploading");
    try {
      const job = await uploadPdfForExtraction(batchId, subjectId, file);
      setStage("processing");
      await pollJob(job.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
      setStage("failed");
    }
  }

  async function pollJob(jobId: string) {
    for (let i = 0; i < 30; i++) {
      const job = await getExtractionJob(jobId);
      if (job.status === "COMPLETED" && job.assessment_id) {
        router.push(`/dashboard/assessments/${job.assessment_id}`);
        return;
      }
      if (job.status === "FAILED") {
        setError(job.error_message ?? "Extraction failed");
        setStage("failed");
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    setError("Extraction is taking longer than expected -- check back later.");
    setStage("failed");
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
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
        <Label htmlFor="pdf">PDF file</Label>
        <Input id="pdf" type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {stage === "processing" && (
        <p className="text-sm text-muted-foreground">Extracting questions... this can take up to a minute.</p>
      )}

      <Button type="submit" disabled={!file || !batchId || !subjectId || stage === "uploading" || stage === "processing"}>
        {stage === "uploading" || stage === "processing" ? "Processing..." : "Upload and extract"}
      </Button>
      <p className="text-xs text-muted-foreground">
        Extracted questions land as a draft for your review -- nothing is published automatically.
      </p>
    </form>
  );
}
