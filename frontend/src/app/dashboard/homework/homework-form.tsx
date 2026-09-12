"use client";

import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  listBatches,
  listSubjects,
  listTopics,
  createHomework,
  type Batch,
  type Subject,
  type Topic,
  ApiError,
} from "@/lib/api";

const schema = z.object({
  batch_id: z.string().min(1, "Select a batch"),
  subject_id: z.string().min(1, "Select a subject"),
  topic_id: z.string().optional(),
  title: z.string().min(1, "Title is required").max(255),
  description: z.string().optional(),
  due_date: z.string().min(1, "Due date is required"),
});

type FormValues = z.infer<typeof schema>;

export function HomeworkForm({ onCreated }: { onCreated: () => void }) {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const subjectId = watch("subject_id");

  useEffect(() => {
    listBatches().then(setBatches).catch(() => setBatches([]));
    listSubjects().then(setSubjects).catch(() => setSubjects([]));
  }, []);

  useEffect(() => {
    if (!subjectId) {
      setTopics([]);
      return;
    }
    listTopics(subjectId).then(setTopics).catch(() => setTopics([]));
  }, [subjectId]);

  async function onSubmit(values: FormValues) {
    setSubmitError(null);
    setSubmitting(true);
    try {
      await createHomework({
        batch_id: values.batch_id,
        subject_id: values.subject_id,
        topic_id: values.topic_id || undefined,
        title: values.title,
        description: values.description || undefined,
        due_date: new Date(values.due_date).toISOString(),
        files,
      });
      reset();
      setFiles([]);
      onCreated();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to create homework");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label>Batch</Label>
          <Select onValueChange={(v: string | null) => setValue("batch_id", v ?? "", { shouldValidate: true })}>
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
          {errors.batch_id && <p className="text-sm text-red-600">{errors.batch_id.message}</p>}
        </div>

        <div className="space-y-1">
          <Label>Subject</Label>
          <Select onValueChange={(v: string | null) => setValue("subject_id", v ?? "", { shouldValidate: true })}>
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
          {errors.subject_id && <p className="text-sm text-red-600">{errors.subject_id.message}</p>}
        </div>
      </div>

      {topics.length > 0 && (
        <div className="space-y-1">
          <Label>Topic (optional)</Label>
          <Select onValueChange={(v: string | null) => setValue("topic_id", v ?? undefined)}>
            <SelectTrigger>
              <SelectValue placeholder="Select topic" />
            </SelectTrigger>
            <SelectContent>
              {topics.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-1">
        <Label htmlFor="title">Title</Label>
        <Input id="title" {...register("title")} />
        {errors.title && <p className="text-sm text-red-600">{errors.title.message}</p>}
      </div>

      <div className="space-y-1">
        <Label htmlFor="description">Instructions</Label>
        <Textarea id="description" {...register("description")} />
      </div>

      <div className="space-y-1">
        <Label htmlFor="due_date">Due date</Label>
        <Input id="due_date" type="datetime-local" {...register("due_date")} />
        {errors.due_date && <p className="text-sm text-red-600">{errors.due_date.message}</p>}
      </div>

      <div className="space-y-1">
        <Label htmlFor="files">Attachments</Label>
        <Input
          id="files"
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
      </div>

      {submitError && <p className="text-sm text-red-600">{submitError}</p>}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Creating..." : "Create homework"}
      </Button>
    </form>
  );
}
