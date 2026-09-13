"use client";

import { use, useEffect, useState } from "react";
import { ListChecks } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import {
  listSubjects,
  getSyllabus,
  markSyllabusTopic,
  type Subject,
  type SyllabusTopic,
  type SyllabusStatus,
  ApiError,
} from "@/lib/api";

const STATUS_OPTIONS: { value: SyllabusStatus; label: string }[] = [
  { value: "NOT_STARTED", label: "Not started" },
  { value: "IN_PROGRESS", label: "In progress" },
  { value: "COMPLETED", label: "Completed" },
];

export default function SyllabusPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: batchId } = use(params);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [topics, setTopics] = useState<SyllabusTopic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    listSubjects()
      .then((data) => {
        setSubjects(data);
        if (data.length > 0) setSubjectId(data[0].id);
      })
      .catch(() => setSubjects([]));
  }, []);

  function load() {
    if (!subjectId) return;
    setError(null);
    getSyllabus(batchId, subjectId)
      .then(setTopics)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load syllabus"));
  }

  useEffect(() => {
    setTopics(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId]);

  async function handleStatusChange(topicId: string, status: SyllabusStatus) {
    if (!subjectId) return;
    setUpdating(topicId);
    try {
      await markSyllabusTopic(topicId, { batch_id: batchId, subject_id: subjectId, status });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update topic");
    } finally {
      setUpdating(null);
    }
  }

  const completedCount = topics?.filter((t) => t.status === "COMPLETED").length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Syllabus checklist"
        description="Mark topics as you cover them -- parents see this as a completion percentage."
        icon={ListChecks}
        action={
          subjects.length > 0 && (
            <Select value={subjectId ?? undefined} onValueChange={(v: string | null) => v && setSubjectId(v)}>
              <SelectTrigger className="w-56">
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
          )
        }
      />

      {subjects.length === 0 && <p className="text-sm text-muted-foreground">Create a subject first.</p>}
      {error && <ErrorBanner message={error} />}

      {topics === null && subjectId && <Skeleton className="h-40 w-full" />}

      {topics !== null && (
        <div className="max-w-2xl space-y-2">
          <p className="text-sm text-muted-foreground">
            {completedCount} of {topics.length} topics completed
          </p>
          {topics.map((topic) => (
            <div
              key={topic.topic_id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3"
            >
              <span className="text-sm font-medium text-foreground">{topic.topic_name}</span>
              <select
                className="rounded-md border border-input bg-transparent px-2 py-1 text-sm"
                value={topic.status}
                disabled={updating === topic.topic_id}
                onChange={(e) => handleStatusChange(topic.topic_id, e.target.value as SyllabusStatus)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
