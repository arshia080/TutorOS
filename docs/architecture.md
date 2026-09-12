# Architecture

TutorOS is a **modular monolith**, deliberately — see [§ Why not microservices](#why-not-microservices).

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
                                                    (Phase 4/6)
                                                          |
                                                     PostgreSQL
                                                          |
                                              +-----------+-----------+
                                              |                       |
                                        File Storage                Redis
                                     (S3-compatible                   |
                                       abstraction)          (provisioned, unused
                                                               -- see below)
```

## Layering (backend)

Every feature follows the same three-layer shape, enforced by convention
(there's no framework magic forcing it — see `docs/development.md` for how to
keep new code consistent):

```
app/api/routes/<feature>.py   Thin. Parses the request, calls one service
                               function, shapes the response. No business logic,
                               no direct SQLAlchemy queries beyond what the
                               service layer returns.
        |
app/services/<feature>_service.py   All business logic, authorization checks,
                                      and the only code that talks to SQLAlchemy
                                      directly. Every "can teacher A see teacher
                                      B's batch" check lives here, not in routes.
        |
app/models/<feature>.py       SQLAlchemy ORM models -- the schema, nothing else.
```

Pydantic schemas (`app/schemas/<feature>.py`) sit alongside routes: they define
request/response shapes and do structural validation (required fields, types,
ranges) before a request ever reaches a service function. Semantic validation
that Pydantic can't express (e.g. "an MCQ needs exactly one correct option")
lives in dedicated modules like `app/services/question_validation.py`.

This mirrors the product spec's own required layering:

```
Router  -> Service -> Repository* -> Database
Router  -> AI Service -> Provider abstraction
Router  -> Analytics Service -> Database
```

\* There's no separate repository layer — service functions query SQLAlchemy
directly. A repository layer would be premature abstraction for a monolith
this size; every service function already has a single, obvious owner of "how
this feature reads its own data."

## Directory layout

```
backend/
  app/
    api/routes/     one file per feature area, thin route handlers
    services/       business logic + authorization, one file per feature
    models/         SQLAlchemy models, one file per feature area
    schemas/        Pydantic request/response models
    ai/             AIProvider abstraction (base.py, anthropic_provider.py) + factory
    storage/        StorageBackend abstraction (base.py, local.py) + factory
    core/           config, security (JWT/bcrypt), logging, error handlers,
                    rate limiting, dependency-injection helpers (deps.py)
    db/             SQLAlchemy engine/session setup
  alembic/          migrations, one per phase's schema additions
  scripts/seed.py   realistic demo data generator (section 35)
  tests/            one file per feature area, mirrors app/services/
frontend/
  src/app/dashboard/<feature>/   one route per feature, App Router
  src/lib/api.ts                 single typed fetch client for the whole app
  src/lib/use-auth.ts            client-side auth guard hook
  src/components/ui/             shadcn/ui primitives
```

## The four provider/backend abstractions

Four places in this codebase exist specifically so a concrete choice (SQLite
vs Postgres, local disk vs S3, one AI vendor vs another, sync vs async
background jobs) can change without touching calling code:

| Abstraction | Interface | Current implementation | Swap point |
|---|---|---|---|
| Database | SQLAlchemy `Session` | SQLite (dev), Postgres (prod) | `DATABASE_URL` env var only |
| File storage | `StorageBackend` (`app/storage/base.py`) | `LocalDiskStorage` (default) or `S3Storage` (MinIO/S3/R2) | `STORAGE_BACKEND` env var, `get_storage()` in `app/storage/__init__.py` |
| AI provider | `AIProvider` (`app/ai/base.py`) | `AnthropicProvider` | `get_ai_provider()` in `app/ai/__init__.py` |
| Background jobs | Celery task (`@celery_app.task`) | Celery + Redis broker | `app/celery_app.py` |

The storage and AI abstractions are real interfaces with exactly one or two
implementations each — not because more are needed today, but because the spec
explicitly calls for the seam ("swapping providers later doesn't touch calling
code"). Adding a second implementation (e.g. `S3Storage`, `OpenAIProvider`)
means writing one new class and changing one factory function.

## Background jobs: Celery + Redis

The product spec asks for Celery/RQ-backed background jobs (PDF processing,
performance recalculation). Phases 0-7 ran these via `FastAPI.BackgroundTasks`
instead, because this project's development environment had no working
Docker/Redis to build or test a real broker against.

Docker/Redis became available after Phase 7, and the swap to real Celery was
exactly as narrow as always planned: each job was already a single function
(`ai_pdf_service.process_extraction_job`,
`analytics_service.recalculate_after_attempt`) taking JSON-serializable
arguments and opening its own DB session. Becoming a Celery task
(`app/celery_app.py`) meant wrapping it with `@celery_app.task` and changing
the call site from `background_tasks.add_task(fn, ...)` to `fn.delay(...)` —
no service-layer logic changed.

Jobs now run in a separate worker process (`celery -A app.celery_app worker
--loglevel=info --pool=solo`), survive a web-process restart, and can scale
across multiple worker processes. The test suite runs Celery in "eager" mode
(`task_always_eager=True`, set in `tests/conftest.py`) so `.delay()` executes
synchronously in-process — the standard Celery testing pattern, needing no
real broker.

## Why not microservices

Explicitly out of scope per the product spec (§39: "do not create unnecessary
microservices... prefer a well-designed modular monolith"). A solo/small-team
EdTech product at this stage gains nothing from network boundaries between
"homework" and "assessments" — it would only add deployment complexity,
distributed-transaction problems (an assessment publish touching homework
data, say), and operational overhead with zero corresponding benefit at this
scale. The service-layer boundaries above give the same logical separation
without the network hop; extracting a real microservice later (if genuine
independent-scaling needs emerge) is a refactor of one service file, not a
rewrite.

## AI/document pipeline

```
PDF upload -> validate (PDF-only, size cap) -> store (storage abstraction)
  -> AIExtractionJob row created, HTTP 202 returned immediately
  -> [BackgroundTask] extract text (pypdf, OCR fallback if near-empty)
  -> AI segmentation into structured questions (AIProvider, forced JSON schema)
  -> two-layer validation gate (Pydantic + semantic option-shape rules)
  -> DRAFT Assessment + Questions created (source="AI_EXTRACTED")
  -> job marked COMPLETED, teacher polls GET /ai/jobs/{id}
  -> teacher reviews (Edit/Delete/Regenerate/Change topic/difficulty/marks)
  -> teacher explicitly publishes (same validator as manually-built assessments)
```

Full detail, including the exact prompts and every validation rule, is in
`docs/ai-pipeline.md`.

## Performance/analytics pipeline

```
Assessment published -> student attempts -> objective questions auto-graded
server-side (never trusts a client-supplied score)
  -> responses persisted immediately per-question (autosave, not one final blob)
  -> compute_topic_performance() reads responses/attempts LIVE on every API call
     (never from a cache -- see docs/analytics.md for why)
  -> mastery/trend surfaced on the Attention Panel, class charts, student dashboard
  -> weak topic (mastery below a configurable threshold) -> "Generate Practice"
  -> practice completion computes a SEPARATE, formula-consistent before/after
     number -- deliberately never rewrites the real exam-based mastery
     (see docs/analytics.md's Personalized Practice section for why)
```

## Frontend

Next.js 16 App Router, one directory per feature under
`src/app/dashboard/<feature>/`, each with its own `page.tsx` (and `[id]/`
subroutes for detail views). No global state management library — every page
fetches what it needs via `src/lib/api.ts`'s typed functions and holds it in
local `useState`; there's no cross-page shared cache because nothing in this
app needs one at its current scale (see `docs/development.md` for when that
calculus would change). Auth is a JWT in `localStorage`, checked client-side
by the `useAuth()` hook, which every `/dashboard/*` page relies on via the
shared `layout.tsx`.

## Deployment shape

No component of this application assumes it's running on any particular host.
See `docs/development.md`'s Deployment section for how to run frontend,
backend, Postgres, object storage, and Redis as independent, separately
deployable pieces.
