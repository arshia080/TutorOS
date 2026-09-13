import Link from "next/link";
import {
  ArrowRight,
  FileText,
  LineChart,
  Sparkles,
  ClipboardCheck,
  ShieldCheck,
  Target,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const STATS = [
  { value: "3", label: "Core roles: teacher, student, and analytics" },
  { value: "4", label: "Weighted signals feed every mastery score" },
  { value: "100%", label: "AI output validated before it touches a grade" },
  { value: "0", label: "Spreadsheets required to run a batch" },
];

const STEPS = [
  {
    number: "01",
    title: "Assess",
    description:
      "Generate a quiz from a topic and difficulty, or upload an existing worksheet — TutorOS extracts and structures the questions for you.",
  },
  {
    number: "02",
    title: "Analyze",
    description:
      "Every response feeds a documented mastery formula, broken down by topic — not a single opaque score.",
  },
  {
    number: "03",
    title: "Personalize",
    description:
      "Weak topics surface automatically. Generate a targeted practice set and watch mastery move, with before/after tracking.",
  },
];

const PILLARS = [
  {
    icon: Sparkles,
    title: "AI-assisted assessment creation",
    description:
      "Describe a grade, subject, and difficulty mix and get a ready-to-publish assessment — MCQs and subjective questions included.",
    points: [
      "Structured output, validated before it ever reaches a student",
      "Regenerate a single weak question without rebuilding the set",
      "Works alongside manually authored questions in the same assessment",
    ],
  },
  {
    icon: FileText,
    title: "PDF-to-quiz extraction",
    description:
      "Upload a worksheet or answer key you already have. TutorOS extracts the questions, matches them to topics, and grades against the key.",
    points: [
      "Handles scanned pages via OCR fallback when text extraction is thin",
      "Teacher reviews and confirms before anything goes live",
      "No manual re-typing of questions you've already written",
    ],
  },
  {
    icon: LineChart,
    title: "Topic-level mastery, explained",
    description:
      "Recent accuracy, historical accuracy, difficulty-adjusted performance, and consistency combine into one auditable score per topic.",
    points: [
      "Every weight and formula documented — nothing is a black box",
      "Trend detection flags improving vs. declining topics automatically",
      "The Attention Panel surfaces exactly who needs help, and where",
    ],
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-lg font-semibold tracking-tight text-foreground">
            Tutor<span className="text-primary">OS</span>
          </Link>
          <nav className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex">
            <a href="#features" className="transition-colors hover:text-foreground">
              Features
            </a>
            <a href="#how-it-works" className="transition-colors hover:text-foreground">
              How it works
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Button variant="ghost" nativeButton={false} render={<Link href="/login">Log in</Link>} />
            <Button nativeButton={false} render={<Link href="/register">Get started</Link>} />
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-border/70">
          <div className="pointer-events-none absolute -top-24 right-0 h-96 w-96 rounded-full bg-accent/50 blur-3xl" />
          <div className="pointer-events-none absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-secondary/60 blur-3xl" />

          <div className="relative mx-auto grid max-w-6xl gap-14 px-6 py-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-28">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
                <span className="size-1.5 rounded-full bg-primary" />
                Built for tutors and small institutes
              </div>

              <h1 className="mt-6 max-w-xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                The operating system for your tutoring practice
              </h1>

              <p className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
                TutorOS replaces the spreadsheets and guesswork with AI-assisted
                assessments, an explainable mastery model, and practice that
                targets exactly what each student needs next.
              </p>

              <div className="mt-9 flex flex-wrap items-center gap-4">
                <Button
                  size="lg"
                  nativeButton={false}
                  render={
                    <Link href="/register" className="gap-2">
                      Get started free
                      <ArrowRight className="size-4" />
                    </Link>
                  }
                />
                <a
                  href="#how-it-works"
                  className="text-sm font-medium text-foreground underline-offset-4 hover:underline"
                >
                  See how it works
                </a>
              </div>

              <p className="mt-6 text-xs text-muted-foreground">
                No credit card required · Set up a batch in minutes
              </p>
            </div>

            {/* Product mockup */}
            <div className="relative">
              <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xl shadow-primary/5">
                <div className="flex items-center gap-1.5 border-b border-border/70 bg-muted/40 px-4 py-3">
                  <span className="size-2.5 rounded-full bg-destructive/40" />
                  <span className="size-2.5 rounded-full bg-accent" />
                  <span className="size-2.5 rounded-full bg-primary/40" />
                  <span className="ml-3 text-xs text-muted-foreground">Class Overview</span>
                </div>
                <div className="space-y-5 p-6">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">Topic mastery — Class 10-A</p>
                    <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                      Live
                    </span>
                  </div>

                  {[
                    { topic: "Algebra", score: 84 },
                    { topic: "Geometry", score: 67 },
                    { topic: "Trigonometry", score: 42 },
                  ].map((row) => (
                    <div key={row.topic} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>{row.topic}</span>
                        <span className="font-medium text-foreground">{row.score}%</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full ${
                            row.score < 50 ? "bg-destructive/70" : "bg-primary"
                          }`}
                          style={{ width: `${row.score}%` }}
                        />
                      </div>
                    </div>
                  ))}

                  <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2.5">
                    <Target className="size-4 shrink-0 text-primary" />
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">Trigonometry</span> flagged on
                      the Attention Panel — practice set ready to generate.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Stats strip */}
        <section className="border-b border-border/70 bg-muted/30">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-6 py-12 sm:grid-cols-4">
            {STATS.map((stat) => (
              <div key={stat.label}>
                <p className="text-3xl font-semibold tracking-tight text-primary">{stat.value}</p>
                <p className="mt-1 text-sm text-muted-foreground">{stat.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-6xl px-6 py-24">
          <div className="max-w-xl">
            <p className="text-sm font-medium uppercase tracking-wider text-primary">
              How it works
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
              Three steps, running continuously
            </h2>
          </div>

          <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
            {STEPS.map((step, i) => (
              <div
                key={step.number}
                className={`relative pl-6 ${i > 0 ? "md:border-l md:border-border md:pl-8" : ""}`}
              >
                <span className="text-sm font-semibold text-primary/70">{step.number}</span>
                <h3 className="mt-2 text-lg font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Feature pillars */}
        <section id="features" className="border-t border-border/70 bg-muted/20">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="max-w-xl">
              <p className="text-sm font-medium uppercase tracking-wider text-primary">
                Built around one idea
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
                Every number should be explainable, every gap actionable
              </h2>
            </div>

            <div className="mt-16 space-y-16">
              {PILLARS.map((pillar, i) => (
                <div
                  key={pillar.title}
                  className={`grid items-start gap-10 md:grid-cols-2 md:gap-16 ${
                    i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
                  }`}
                >
                  <div className="flex items-center justify-center rounded-xl border border-border bg-card p-12 shadow-sm">
                    <pillar.icon className="size-16 text-primary" strokeWidth={1.25} />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-foreground">{pillar.title}</h3>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      {pillar.description}
                    </p>
                    <ul className="mt-5 space-y-2.5">
                      {pillar.points.map((point) => (
                        <li key={point} className="flex items-start gap-2.5 text-sm text-foreground">
                          <ClipboardCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Security note */}
        <section className="mx-auto max-w-6xl px-6 py-20">
          <div className="flex flex-col items-start gap-6 rounded-xl border border-border bg-card p-8 shadow-sm sm:flex-row sm:items-center">
            <ShieldCheck className="size-10 shrink-0 text-primary" strokeWidth={1.5} />
            <div>
              <h3 className="text-lg font-semibold text-foreground">
                Role-based access, by design
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Teachers and students see only what they should. Every score a student sees was
                computed server-side — never trusted from the client.
              </p>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="border-t border-border/70">
          <div className="mx-auto max-w-6xl px-6 py-20 text-center">
            <h2 className="text-3xl font-semibold tracking-tight text-foreground">
              Set up your first batch today
            </h2>
            <p className="mx-auto mt-3 max-w-md text-muted-foreground">
              Create an account, add a batch and subject, and publish your first assessment in
              minutes.
            </p>
            <div className="mt-8">
              <Button
                size="lg"
                nativeButton={false}
                render={
                  <Link href="/register" className="gap-2">
                    Create your account
                    <ArrowRight className="size-4" />
                  </Link>
                }
              />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/70">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-muted-foreground sm:flex-row">
          <span className="font-medium text-foreground">
            Tutor<span className="text-primary">OS</span>
          </span>
          <span>© {new Date().getFullYear()} TutorOS. Built for tutors who want their data to mean something.</span>
        </div>
      </footer>
    </div>
  );
}
