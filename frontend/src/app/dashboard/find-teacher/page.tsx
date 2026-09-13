"use client";

import { useState } from "react";
import { Search, MapPin, GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import { searchTeachers, type TeacherSearchResult, ApiError } from "@/lib/api";

export default function FindTeacherPage() {
  const [locality, setLocality] = useState("");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [results, setResults] = useState<TeacherSearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await searchTeachers({
        locality: locality || undefined,
        subject: subject || undefined,
        grade: grade || undefined,
      });
      setResults(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Find a teacher"
        description="Search by locality, subject, or grade. No account required to browse."
        icon={Search}
      />

      <Card className="max-w-2xl border-0 shadow-sm ring-1 ring-border">
        <CardContent className="py-4">
          <form onSubmit={handleSearch} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Input placeholder="Locality or city" value={locality} onChange={(e) => setLocality(e.target.value)} />
            <Input placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <Input placeholder="Grade" value={grade} onChange={(e) => setGrade(e.target.value)} />
            <Button type="submit" disabled={loading} className="gap-1.5">
              <Search className="size-4" />
              {loading ? "Searching..." : "Search"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && <ErrorBanner message={error} />}

      {results !== null && results.length === 0 && !error && (
        <EmptyState icon={Search} title="No teachers found" description="Try a broader search." />
      )}

      {results !== null && results.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {results.map((t) => (
            <Card key={t.teacher_id} className="border-0 shadow-sm ring-1 ring-border">
              <CardContent className="py-4">
                <p className="font-medium text-foreground">{t.name}</p>
                {t.institute_name && <p className="text-sm text-muted-foreground">{t.institute_name}</p>}
                {(t.locality || t.city) && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="size-3" />
                    {[t.locality, t.city].filter(Boolean).join(", ")}
                  </p>
                )}
                {t.bio && <p className="mt-2 text-sm text-muted-foreground">{t.bio}</p>}
                {t.subjects.length > 0 && (
                  <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                    <GraduationCap className="size-3" />
                    {t.subjects.join(", ")}
                    {t.grades.length > 0 && ` · Grades ${t.grades.join(", ")}`}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        To connect with a teacher, use &quot;Link a child&quot; from your dashboard with an invite code from them,
        or request a link by your child&apos;s account email.
      </p>
    </div>
  );
}
