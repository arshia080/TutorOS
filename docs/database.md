# Database

PostgreSQL in production, SQLite for local dev/tests (see
[§ Why SQLite in dev](#why-sqlite-in-dev)). All models use SQLAlchemy 2.0's
dialect-generic types (`Uuid`, `Enum`, `DateTime`) specifically so the same
migration runs unmodified on both.

## Migrations (in order)

| Migration | Adds |
|---|---|
| `eb78b5d0bb29` | `users` |
| `f19e11a0e3a0` | `teacher_profiles`, `student_profiles`, `batches`, `batch_students`, `subjects`, `topics` |
| `50b9bb1bd83c` | `homework`, `homework_attachments`, `homework_submissions` |
| `68ec7a248ed1` | `assessments`, `questions`, `question_options`, `assessment_attempts`, `responses`, `response_selected_options` |
| `79a12d96eb03` | `performance_snapshots`, `attendance` |
| `ac062c8628b6` | `ai_extraction_jobs` |
| `038ae11f1e8f` | `practice_sets`, `practice_questions`, `practice_question_options`, `practice_responses`, `recommendations` |

Run `alembic upgrade head` after cloning; `alembic revision --autogenerate -m "..."`
after changing any model, then read the generated file before committing it
(autogenerate is a starting point, not a guarantee — see `docs/development.md`).

## Entity groups

### Identity
`users` (id, name, email, password_hash, role, timestamps) is the single
identity table for all four roles (`TEACHER`, `STUDENT`, `PARENT` — unused,
`ADMIN` — unused). `teacher_profiles`/`student_profiles` hold role-specific
optional fields (institute name/bio; grade/academic year), 1:1 with `users`.

### Academic structure
`batches` (owned by a `teacher_id`) `<->` `batch_students` (many-to-many,
composite PK `(batch_id, student_id)`, carries `status` so removing a student
is a soft state change, not a delete) `<->` `users`. `subjects`/`topics` are
**global catalog data, not batch-owned** — any teacher can create/see any
subject or topic. This matches the schema the product spec literally
describes; if per-teacher subject scoping is ever needed, that's a schema
change (an owner column), not a bug fix.

### Homework
`homework` (batch/subject/topic-tagged, due date, `allow_late_submissions`
flag) `->` `homework_attachments` (teacher's files) and
`homework_submissions` (one per student per homework, `UniqueConstraint` on
`(homework_id, student_id)` — resubmission overwrites the same row rather than
accumulating history). Both attachment tables store a randomized
`storage_key` plus a display `file_name`; the storage key is never returned
by any API response (see `docs/security.md`).

### Assessment engine
`assessments` (status `DRAFT/REVIEW/PUBLISHED/CLOSED`) `->` `questions`
(one of six `question_type`s) `->` `question_options`. A student's
`assessment_attempts` row (`UniqueConstraint(assessment_id, student_id)` — one
attempt per assessment, no retakes) has many `responses`
(`UniqueConstraint(attempt_id, question_id)` — autosave upserts, doesn't
duplicate). `response_selected_options` is a join table for
MCQ/MULTI_SELECT/TRUE_FALSE selections — **the one deliberate structural
deviation from the product spec's literal schema**: the spec sketches a
single `selected_option` column on `responses`, which cannot represent
MULTI_SELECT's "more than one chosen option." The join table replaces it,
used for all selectable types (one row for single-select, N rows for
multi-select) for a single consistent mechanism.

### Analytics
`performance_snapshots` (`UniqueConstraint(student_id, topic_id)`) is a
**write-only cache** — `analytics_service.compute_topic_performance()` is the
only source of truth, always computed live from `responses`/
`assessment_attempts` on every API read; the snapshot table is populated by a
background recalculation job but never read back by the live API, so it can
never itself be a source of staleness bugs. `attendance`
(`UniqueConstraint(batch_id, student_id, date)` — marking twice on the same
day overwrites, doesn't duplicate).

### AI
`ai_extraction_jobs` tracks a PDF-to-assessment background job's status
(`PENDING/PROCESSING/COMPLETED/FAILED`) so the triggering request can return
immediately and the teacher can poll — **not in the product spec's literal
table list**, added because "returns immediately with a job id, teacher
polls" is meaningless without somewhere to persist that status.

### Personalization
`practice_sets` (snapshots `mastery_before`/`mastery_after` — see
`docs/analytics.md` for exactly how the "after" number is derived) `->`
`practice_questions` `->` `practice_question_options`, with
`practice_responses` recording each answer (a plain nullable FK to the
selected option, not a join table — safe specifically because practice
questions are restricted to single-answer types; see the `ponytail:` comment
on `PRACTICE_QUESTION_TYPES` in `app/models/practice.py`). `recommendations`
logs each generated practice set (`status PENDING -> COMPLETED`) with a
`priority` derived from how far below the weak-topic threshold the student's
mastery was.

## Indexes and constraints

Every foreign key that's queried by (not just joined through) has an index:
`teacher_id`/`batch_id`/`student_id`/`topic_id`/`assessment_id`/etc. columns
across every table. Composite primary keys (`batch_students`) or explicit
`UniqueConstraint`s (everywhere else "one row per X per Y" matters) enforce
the "exactly one" invariants at the database level, not just in application
code — a race condition in the app layer still can't produce two `responses`
rows for the same `(attempt_id, question_id)`.

## Why SQLite in dev

Docker Desktop has not had a working engine in this project's development
environment across any phase (see `docs/PROGRESS.md`) — there has never been
a way to run the `docker-compose.yml`-provisioned Postgres locally here. Every
model uses SQLAlchemy's dialect-generic types specifically so this isn't a
divergence in schema behavior, only in the underlying engine; the same
migrations, the same ORM code, and the same test suite all run unmodified
against real Postgres. `backend/.env`'s `DATABASE_URL` is the only thing that
changes between the two.
