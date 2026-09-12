"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  generateQuestions,
  listBatches,
  listSubjects,
  listTopics,
  type Batch,
  type Subject,
  type Topic,
  type QuestionType,
  ApiError,
} from "@/lib/api";

const QUESTION_TYPES: QuestionType[] = ["MCQ", "MULTI_SELECT", "TRUE_FALSE", "NUMERICAL", "SHORT_ANSWER", "LONG_ANSWER"];

export function AIGenerateForm() {
  const router = useRouter();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);

  const [batchId, setBatchId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [grade, setGrade] = useState("10");
  const [count, setCount] = useState("5");
  const [difficulty, setDifficulty] = useState("MEDIUM");
  const [types, setTypes] = useState<QuestionType[]>(["MCQ"]);
  const [totalMarks, setTotalMarks] = useState("10");
  const [duration, setDuration] = useState("20");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  function toggleType(t: QuestionType) {
    setTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const assessment = await generateQuestions({
        batch_id: batchId,
        subject_id: subjectId,
        topic_id: topicId || undefined,
        grade,
        count: Number(count),
        difficulty,
        question_types: types,
        total_marks: Number(totalMarks),
        duration_minutes: Number(duration),
      });
      router.push(`/dashboard/assessments/${assessment.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate questions");
    } finally {
      setSubmitting(false);
    }
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

      {topics.length > 0 && (
        <div className="space-y-1">
          <Label>Topic (optional)</Label>
          <Select onValueChange={(v: string | null) => setTopicId(v ?? "")}>
            <SelectTrigger>
              <SelectValue placeholder="Any topic" />
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

      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1">
          <Label htmlFor="grade">Grade</Label>
          <Input id="grade" value={grade} onChange={(e) => setGrade(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="count"># Questions</Label>
          <Input id="count" type="number" min={1} max={20} value={count} onChange={(e) => setCount(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Difficulty</Label>
          <Select value={difficulty} onValueChange={(v: string | null) => v && setDifficulty(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="EASY">Easy</SelectItem>
              <SelectItem value="MEDIUM">Medium</SelectItem>
              <SelectItem value="HARD">Hard</SelectItem>
              <SelectItem value="MIXED">Mixed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1">
        <Label>Question types</Label>
        <div className="flex flex-wrap gap-3">
          {QUESTION_TYPES.map((t) => (
            <label key={t} className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={types.includes(t)} onChange={() => toggleType(t)} />
              {t}
            </label>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="total_marks">Total marks</Label>
          <Input id="total_marks" type="number" min={1} value={totalMarks} onChange={(e) => setTotalMarks(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="duration">Duration (minutes)</Label>
          <Input id="duration" type="number" min={1} value={duration} onChange={(e) => setDuration(e.target.value)} />
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <Button type="submit" disabled={submitting || !batchId || !subjectId || types.length === 0}>
        {submitting ? "Generating..." : "Generate with AI"}
      </Button>
      <p className="text-xs text-muted-foreground">
        Generated questions land as a draft for your review -- nothing is published automatically.
      </p>
    </form>
  );
}
