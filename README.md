# TutorOS

**AI-powered academic operating system for tutors.**

A full-stack academic management and personalized learning platform for
local tuition teachers and small coaching institutes — built as a
portfolio-grade EdTech SaaS product, not a college CRUD project.

## The problem

Local tutors run their practice on fragmented tools: WhatsApp for homework,
notebooks for marks, spreadsheets for performance, Google Forms for quizzes,
PDFs for tests, and manual, error-prone identification of which students are
struggling with what. The interesting problem isn't "how does a teacher
manage a student list" — it's:

> How can assessment data help a teacher understand exactly where every
> student is struggling and decide what to teach or assign next?

Student performance intelligence is the core of this product, not an
afterthought bolted onto a CRUD app.

## The core loop

**Teach → Assign → Assess → Analyze → Identify gaps → Personalize → Improve**

Concretely: a teacher uploads an existing PDF test, AI extracts and structures
the questions for review, the teacher publishes it, students take it online
with objective questions auto-graded server-side, topic-level mastery updates
in real time, a weak topic surfaces on the teacher's Attention Panel, and a
personalized AI-generated practice set targets exactly that gap — with the
before/after improvement always presented as an observed change, never a
proven causal claim.

## Features

- **Academic management**: teachers, batches, subjects, topics, students — with resource-level authorization enforced server-side throughout (a teacher can never read another teacher's batch; a student can never read another student's data).
- **Homework**: creation with attachments, deadline enforcement, submission tracking (submitted/pending/late), teacher review.
- **Online assessments**: 6 question types, countdown timer with server-side expiry enforcement, autosave, backend-authoritative grading (a score is never trusted from the client) for objective questions, teacher grading for subjective ones.
- **Performance analytics**: topic-level accuracy, a documented weighted mastery formula, deterministic trend detection, class-wide analytics, attendance tracking — all computed live, never hardcoded, with an explicit methodology writeup (`docs/analytics.md`).
- **AI features**: question generation, PDF-to-assessment extraction (with a real document-processing pipeline, not a stub), and performance insights that are checked for fabricated statistics before being shown to anyone. AI-generated content always lands as a draft for teacher review — never auto-published.
- **Personalized practice**: weak-topic detection, AI-generated practice sets with a configurable easy/medium/hard mix, and a before/after mastery comparison that's honest about correlation vs. causation.

## Architecture

```
                              TutorOS
                                 |
                +----------------+----------------+
                |                                 |
             Frontend                          Backend
          Next.js 16 / React                    FastAPI
                |                                 |
                |         +----------+------------+------------+-----------+
                |         |          |            |             |          |
                |       Auth     Academic     Homework     Assessment      AI
                |                 (batches,     engine       engine      Engine
                |                 subjects,                (Phase 3)   (Phase 5)
                |                 students)
                |         |          |            |             |          |
                +---------+----------+------------+------+------+----------+
                                                          |
                                                     Analytics
                                                          |
                                                     PostgreSQL
                                                          |
                                              +-----------+-----------+
                                              |                       |
                                        File Storage                Redis
                                     (S3-compatible           (Celery job
                                       abstraction)              broker)
```

Full detail (background jobs via Celery + Redis, why no
microservices, the AI pipeline diagram, the four provider abstractions) in
**[`docs/architecture.md`](docs/architecture.md)**.

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL (SQLite in dev — see below) |
| Auth | JWT (HS256), bcrypt password hashing |
| File storage | Abstracted (`StorageBackend`); local disk in dev |
| Background jobs | Celery + Redis |
| AI | Anthropic API via a swappable `AIProvider` abstraction |
| Testing | Pytest, 130+ tests, zero real external API calls |

## Documentation

| Doc | Covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System design, layering, the four provider abstractions, Celery/Redis background jobs, why no microservices |
| [`docs/database.md`](docs/database.md) | Schema, migrations, every entity group, the one deliberate schema deviation from the spec |
| [`docs/api.md`](docs/api.md) | Full endpoint reference by feature area |
| [`docs/ai-pipeline.md`](docs/ai-pipeline.md) | Question generation, PDF extraction, performance insights — prompts, validation gates, limitations |
| [`docs/analytics.md`](docs/analytics.md) | The mastery formula, trend detection rule, personalized-practice before/after methodology, causation disclaimers |
| [`docs/security.md`](docs/security.md) | Full security posture, what was audited and fixed, what a real deployment must change |
| [`docs/development.md`](docs/development.md) | Local setup, seeding, testing, logging, deployment, deferred items |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | The full build log across all 7 phases — decisions, trade-offs, what was verified live vs. only in tests |

## Local setup

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on mac/linux
pip install -r requirements.txt
copy .env.example .env      # cp on mac/linux
alembic upgrade head
python -m scripts.seed      # realistic demo data (3 teachers, 40 students, hundreds of responses)
uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal) -- required for PDF extraction / analytics jobs
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo   # drop --pool=solo on mac/linux

# Frontend (separate terminal)
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Visit `http://localhost:3000/register`, or log in as a seeded account —
every seeded user's password is `password123` (e.g.
`priya.nair@tutoros.dev` for a teacher, `rahul.sharma@tutoros.dev` for a
student with a real weak-topic trajectory). Full setup detail, running
without Docker, and seed-data specifics in
**[`docs/development.md`](docs/development.md)**.

### Environment variables

See `.env.example` in each of `backend/` and `frontend/` for the full,
current list. `ANTHROPIC_API_KEY` is the only optional one — every AI feature
degrades to a clear `502` error without it rather than crashing; everything
else in the app works fully without a key configured.

### Database migrations

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "description"  # after changing a model
```

### Tests

```bash
cd backend
pytest -q
```

130+ tests, zero real external API calls (the AI provider is mocked via a
test double satisfying the same interface the real one does).

## Deployment

Frontend, backend, PostgreSQL, object storage, and Redis are all
independently deployable — nothing in this codebase assumes a specific host,
region, or that any two of these run on the same machine. Full checklist
(what must change from the dev defaults before going live) in
**[`docs/development.md`](docs/development.md#deployment)** and
**[`docs/security.md`](docs/security.md#what-a-real-deployment-must-change)**.

## Screenshots

_Not included in this repository — run the app locally against the seeded
demo data (above) to see the actual UI; it reflects real computed data, not
static mockups._

## Engineering decisions

**Why PostgreSQL?** Relational integrity matters here — a student's
attempt/response/attendance data has real foreign-key relationships that
benefit from database-enforced constraints, and the analytics engine leans on
SQL joins and aggregates that a document store would make substantially
harder to get right (and to keep provably correct, given how central the
mastery formula's exhaustively-tested correctness is to this product).

**Why FastAPI?** Native Pydantic integration gives structural request/response
validation for free at every endpoint — critical for a product whose central
claim is "we never trust a client-supplied score" and "AI output is always
validated before touching the database." Async support matters for the
AI-backed endpoints; background jobs (PDF extraction, analytics
recalculation) run out-of-process via Celery + Redis.

**Why Next.js?** Server-rendered React with a conventional file-based router
kept the frontend's growth (14 feature areas by Phase 7) organized without
needing a separate routing library or a hand-rolled build pipeline.

**Why Celery + Redis for background jobs?** The product spec calls for
Celery/RQ-backed jobs (PDF processing, performance recalculation). Phases 0-7
ran these via FastAPI's `BackgroundTasks` instead, because the development
environment had no working Docker/Redis to build or test a real broker
against; once Docker/Redis became available, the swap was exactly as narrow
as always planned — one `@celery_app.task` decorator and one call-site change
(`fn.delay(...)`) per job, with no service-layer logic changes. See
`docs/architecture.md`.

**Why topic-level analytics, not just an overall score?** The product's whole
thesis is that "how can a teacher find and address a specific gap" matters
more than "what's the average score" — an aggregate score can't tell a
teacher that a student is strong everywhere except Trigonometry. Topic-level
mastery is what makes the Attention Panel and personalized practice possible
at all.

**Why a documented, product-defined mastery model instead of "the AI decides"
or a black-box ML score?** Every number this system produces needs to be
explainable to a teacher who will act on it — `docs/analytics.md` documents
the exact formula, every weight, and a worked example specifically so nothing
about a student's mastery score is a mystery, and so the explicit disclaimer
("this is a heuristic, not a validated measurement") is impossible to miss.

## What I'd prioritize next

If this became a real product, in rough order:

1. **Pagination** on list endpoints — fine today, would bite at real institute scale (hundreds of students, years of assessment history).
2. **Parent role** — explicitly deferred per the product spec's own MVP scope (§3); the schema already accommodates it (`UserRole.PARENT` exists, unused).
3. **Partial credit / rubric-based subjective grading** — today a teacher enters one score per subjective response; richer rubric support would help larger institutes standardize grading across multiple teachers.
6. **A real evaluation of the mastery formula against actual learning outcomes** — it's explicitly documented as a product-defined heuristic, not validated against real pedagogical research; a real deployment with real usage data is the only way to responsibly improve on that.
