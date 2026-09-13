"use client";

import { useEffect, useState } from "react";
import { BookOpen, ListTree } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import {
  listSubjects,
  createSubject,
  listTopics,
  createTopic,
  type Subject,
  type Topic,
  ApiError,
} from "@/lib/api";

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [subjectName, setSubjectName] = useState("");
  const [subjectGrade, setSubjectGrade] = useState("");
  const [subjectSubmitting, setSubjectSubmitting] = useState(false);

  const [topicName, setTopicName] = useState("");
  const [topicChapter, setTopicChapter] = useState("");
  const [topicSubmitting, setTopicSubmitting] = useState(false);
  const [topicError, setTopicError] = useState<string | null>(null);

  function loadSubjects() {
    setError(null);
    listSubjects()
      .then((data) => {
        setSubjects(data);
        if (data.length > 0 && !selectedSubjectId) setSelectedSubjectId(data[0].id);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load subjects"));
  }

  useEffect(loadSubjects, []);

  useEffect(() => {
    if (!selectedSubjectId) {
      setTopics([]);
      return;
    }
    setTopics(null);
    listTopics(selectedSubjectId)
      .then(setTopics)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load topics"));
  }, [selectedSubjectId]);

  async function handleCreateSubject(e: React.FormEvent) {
    e.preventDefault();
    setSubjectSubmitting(true);
    try {
      const subject = await createSubject({ name: subjectName, grade: subjectGrade || undefined });
      setSubjectName("");
      setSubjectGrade("");
      loadSubjects();
      setSelectedSubjectId(subject.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create subject");
    } finally {
      setSubjectSubmitting(false);
    }
  }

  async function handleCreateTopic(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedSubjectId) return;
    setTopicError(null);
    setTopicSubmitting(true);
    try {
      await createTopic({ subject_id: selectedSubjectId, name: topicName, chapter: topicChapter || undefined });
      setTopicName("");
      setTopicChapter("");
      listTopics(selectedSubjectId).then(setTopics);
    } catch (err) {
      setTopicError(err instanceof ApiError ? err.message : "Failed to create topic");
    } finally {
      setTopicSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Subjects & topics" description="Organize what you teach, by subject and topic." icon={BookOpen} />
      {error && <ErrorBanner message={error} />}

      <div className="grid gap-5 md:grid-cols-2">
        <Card className="border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="size-4 text-primary" />
              Subjects
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateSubject} className="mb-4 flex gap-2">
              <Input
                placeholder="Subject name"
                required
                value={subjectName}
                onChange={(e) => setSubjectName(e.target.value)}
              />
              <Input
                placeholder="Grade"
                className="w-24"
                value={subjectGrade}
                onChange={(e) => setSubjectGrade(e.target.value)}
              />
              <Button type="submit" disabled={subjectSubmitting}>
                Add
              </Button>
            </form>

            {subjects === null && <Skeleton className="h-24 w-full" />}
            {subjects !== null && subjects.length === 0 && (
              <p className="text-sm text-muted-foreground">No subjects yet.</p>
            )}
            <ul className="space-y-1">
              {subjects?.map((s) => (
                <li key={s.id}>
                  <button
                    onClick={() => setSelectedSubjectId(s.id)}
                    className={`w-full rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                      selectedSubjectId === s.id
                        ? "bg-primary text-primary-foreground"
                        : "text-foreground hover:bg-muted"
                    }`}
                  >
                    {s.name}{" "}
                    {s.grade && (
                      <span className={selectedSubjectId === s.id ? "opacity-80" : "text-muted-foreground"}>
                        · Grade {s.grade}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="border-0 shadow-sm ring-1 ring-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ListTree className="size-4 text-primary" />
              Topics
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedSubjectId && (
              <p className="text-sm text-muted-foreground">Select a subject to manage its topics.</p>
            )}

            {selectedSubjectId && (
              <>
                <form onSubmit={handleCreateTopic} className="mb-4 space-y-2">
                  <div className="flex gap-2">
                    <Input
                      placeholder="Topic name"
                      required
                      value={topicName}
                      onChange={(e) => setTopicName(e.target.value)}
                    />
                    <Input
                      placeholder="Chapter"
                      className="w-32"
                      value={topicChapter}
                      onChange={(e) => setTopicChapter(e.target.value)}
                    />
                    <Button type="submit" disabled={topicSubmitting}>
                      Add
                    </Button>
                  </div>
                  {topicError && <ErrorBanner message={topicError} />}
                </form>

                {topics === null && <Skeleton className="h-24 w-full" />}
                {topics !== null && topics.length === 0 && (
                  <p className="text-sm text-muted-foreground">No topics for this subject yet.</p>
                )}
                <ul className="space-y-1">
                  {topics?.map((t) => (
                    <li key={t.id} className="rounded-md px-2.5 py-2 text-sm text-foreground">
                      {t.name} {t.chapter && <span className="text-muted-foreground">· {t.chapter}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
