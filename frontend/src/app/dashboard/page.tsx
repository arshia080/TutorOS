"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LayoutGrid, Users, Sparkles, TrendingUp, UserPlus, Check, X, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState } from "@/components/empty-state";
import { StatCard } from "@/components/stat-card";
import { TrendArrow } from "@/components/trend-arrow";
import {
  getDashboard,
  getStudentPerformance,
  generatePractice,
  listPendingLinkRequests,
  approveLinkRequest,
  rejectLinkRequest,
  listChildren,
  createLinkRequestByCode,
  createLinkRequestByEmail,
  type DashboardOverview,
  type StudentPerformance,
  type PendingLinkRequest,
  type Child,
  ApiError,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

export default function DashboardOverviewPage() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.role === "TEACHER") return <TeacherOverview name={user.name} />;
  if (user.role === "PARENT") return <ParentOverview name={user.name} />;
  return <StudentOverview studentId={user.id} name={user.name} />;
}

function TeacherOverview({ name }: { name: string }) {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingLinkRequest[] | null>(null);
  const [actingOn, setActingOn] = useState<string | null>(null);

  function loadPending() {
    listPendingLinkRequests()
      .then(setPending)
      .catch(() => setPending([]));
  }

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard"));
    loadPending();
  }, []);

  async function handleDecision(linkId: string, decision: "approve" | "reject") {
    setActingOn(linkId);
    try {
      if (decision === "approve") await approveLinkRequest(linkId);
      else await rejectLinkRequest(linkId);
      loadPending();
    } finally {
      setActingOn(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title={`Welcome back, ${name.split(" ")[0]}`} description="A quick look at your batches and students." />

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-2 gap-4 sm:max-w-md">
        <StatCard label="Total batches" value={data === null ? null : data.total_batches} icon={LayoutGrid} />
        <StatCard label="Total students" value={data === null ? null : data.total_students} icon={Users} />
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Parent link requests
        </h2>
        {pending === null && <p className="text-sm text-muted-foreground">Loading...</p>}
        {pending !== null && pending.length === 0 && (
          <p className="text-sm text-muted-foreground">No pending requests from parents right now.</p>
        )}
        {pending !== null && pending.length > 0 && (
          <div className="space-y-2">
            {pending.map((req) => (
              <Card key={req.id} className="border-0 shadow-sm ring-1 ring-border">
                <CardContent className="flex items-center justify-between py-3">
                  <p className="text-sm text-foreground">
                    <span className="font-medium">{req.parent_name}</span> ({req.parent_email}) wants to connect to{" "}
                    <span className="font-medium">{req.student_name}</span>
                    {req.relationship && <span className="text-muted-foreground"> · {req.relationship}</span>}
                  </p>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      size="sm"
                      className="gap-1.5"
                      disabled={actingOn === req.id}
                      onClick={() => handleDecision(req.id, "approve")}
                    >
                      <Check className="size-3.5" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5"
                      disabled={actingOn === req.id}
                      onClick={() => handleDecision(req.id, "reject")}
                    >
                      <X className="size-3.5" />
                      Reject
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ParentOverview({ name }: { name: string }) {
  const [children, setChildren] = useState<Child[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLinkForm, setShowLinkForm] = useState(false);

  function load() {
    setError(null);
    listChildren()
      .then(setChildren)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load children"));
  }

  useEffect(load, []);

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Welcome back, ${name.split(" ")[0]}`}
        description="Track your children's progress across every linked account."
        action={
          <Button className="gap-1.5" onClick={() => setShowLinkForm((v) => !v)}>
            {!showLinkForm && <UserPlus className="size-4" />}
            {showLinkForm ? "Cancel" : "Link a child"}
          </Button>
        }
      />

      {showLinkForm && (
        <LinkChildForm
          onLinked={() => {
            setShowLinkForm(false);
            load();
          }}
        />
      )}

      {error && <ErrorBanner message={error} />}

      {children !== null && children.length === 0 && !error && (
        <EmptyState
          icon={UserPlus}
          title="No linked children yet"
          description="Enter an invite code from your child's teacher, or request a link by their school email."
          action={<Button onClick={() => setShowLinkForm(true)}>Link a child</Button>}
        />
      )}

      {children !== null && children.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {children.map((child) => (
            <Link key={child.student_id} href={`/dashboard/children/${child.student_id}`}>
              <Card className="border-0 shadow-sm ring-1 ring-border transition-shadow hover:shadow-md">
                <CardContent className="py-4">
                  <p className="font-medium text-foreground">{child.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {child.relationship ?? "Linked"}
                    {child.grade && ` · Grade ${child.grade}`}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function LinkChildForm({ onLinked }: { onLinked: () => void }) {
  const [mode, setMode] = useState<"code" | "email">("code");
  const [code, setCode] = useState("");
  const [studentEmail, setStudentEmail] = useState("");
  const [relationship, setRelationship] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      if (mode === "code") {
        await createLinkRequestByCode(code.trim(), relationship || undefined);
        setSuccess("Linked! Your child's data is now visible below.");
      } else {
        await createLinkRequestByEmail(studentEmail.trim(), relationship || undefined);
        setSuccess("Request sent -- the teacher needs to approve it before you can see any data.");
      }
      setCode("");
      setStudentEmail("");
      setRelationship("");
      onLinked();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit link request");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="max-w-md border-0 shadow-sm ring-1 ring-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <KeyRound className="size-4 text-primary" />
          Link a child
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex gap-2">
          <Button type="button" size="sm" variant={mode === "code" ? "default" : "outline"} onClick={() => setMode("code")}>
            Enter invite code
          </Button>
          <Button type="button" size="sm" variant={mode === "email" ? "default" : "outline"} onClick={() => setMode("email")}>
            Request to connect
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "code" ? (
            <div className="space-y-1">
              <Label htmlFor="code">Invite code from teacher</Label>
              <Input id="code" required value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. 2B8D05BE" />
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="student_email">Child's account email</Label>
              <Input
                id="student_email"
                type="email"
                required
                value={studentEmail}
                onChange={(e) => setStudentEmail(e.target.value)}
              />
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="relationship">Relationship (optional)</Label>
            <Input id="relationship" value={relationship} onChange={(e) => setRelationship(e.target.value)} placeholder="Mother, Father, Guardian..." />
          </div>
          {error && <ErrorBanner message={error} />}
          {success && <p className="text-sm text-primary">{success}</p>}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Submitting..." : mode === "code" ? "Link now" : "Send request"}
          </Button>
          {mode === "email" && (
            <p className="text-xs text-muted-foreground">
              Your child's teacher must approve this before any data becomes visible to you.
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

function StudentOverview({ studentId, name }: { studentId: string; name: string }) {
  const router = useRouter();
  const [perf, setPerf] = useState<StudentPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    getStudentPerformance(studentId)
      .then(setPerf)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load performance"));
  }, [studentId]);

  async function handleGeneratePractice(topicId: string) {
    setGenerateError(null);
    setGeneratingTopicId(topicId);
    try {
      const practiceSet = await generatePractice(studentId, topicId);
      router.push(`/dashboard/practice/${practiceSet.id}`);
    } catch (err) {
      setGenerateError(err instanceof ApiError ? err.message : "Failed to generate practice set");
      setGeneratingTopicId(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title={`Welcome back, ${name.split(" ")[0]}`} description="Here's where your progress stands." />

      {error && <ErrorBanner message={error} />}

      {!error && perf === null && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="border-0 shadow-sm ring-1 ring-border">
              <CardContent className="h-20 animate-pulse rounded-md bg-muted/60" />
            </Card>
          ))}
        </div>
      )}

      {perf !== null && perf.topics.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-muted/20 px-6 py-14 text-center text-sm text-muted-foreground">
          No graded test results yet — your progress will show up here once you&apos;ve completed a test.
        </div>
      )}

      {perf !== null && perf.topics.length > 0 && (
        <>
          <div className="max-w-xs">
            <StatCard label="Overall mastery" value={`${perf.overall_mastery}%`} icon={TrendingUp} />
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Strengths</CardTitle>
              </CardHeader>
              <CardContent>
                {perf.strengths.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No topics above 75% mastery yet.</p>
                ) : (
                  <ul className="space-y-2.5">
                    {perf.strengths.map((t) => (
                      <li key={t.topic_id} className="flex items-center justify-between text-sm">
                        <span className="text-foreground">{t.topic_name}</span>
                        <span className="font-medium text-primary">{t.mastery_score}%</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm ring-1 ring-border">
              <CardHeader>
                <CardTitle className="text-base">Needs practice</CardTitle>
              </CardHeader>
              <CardContent>
                {generateError && (
                  <div className="mb-3">
                    <ErrorBanner message={generateError} />
                  </div>
                )}
                {perf.weak_topics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No weak topics right now.</p>
                ) : (
                  <ul className="space-y-3">
                    {perf.weak_topics.map((t) => (
                      <li key={t.topic_id} className="flex items-center justify-between gap-3 text-sm">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate text-foreground">{t.topic_name}</span>
                          <span className="shrink-0 font-medium text-destructive">{t.mastery_score}%</span>
                          <TrendArrow trend={t.trend} />
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          className="shrink-0 gap-1.5"
                          disabled={generatingTopicId === t.topic_id}
                          onClick={() => handleGeneratePractice(t.topic_id)}
                        >
                          <Sparkles className="size-3.5" />
                          {generatingTopicId === t.topic_id ? "Generating..." : "Generate practice"}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground">
            <Link href="/dashboard/assessments" className="font-medium text-primary underline-offset-4 hover:underline">
              View your tests
            </Link>{" "}
            for details. Mastery is a product-defined estimate, not a certified measurement of ability.
          </p>
        </>
      )}
    </div>
  );
}
