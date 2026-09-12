# API reference

This is a curated guide to the API's shape and rules. For the full,
always-current field-level schema, run the backend and open
**`http://localhost:8000/docs`** (Swagger UI, auto-generated from the
Pydantic schemas) or fetch `/openapi.json` directly — those are generated
from the same code this document describes, so they can't drift from it the
way a hand-maintained field list would.

## Base URL, auth, errors

- Base URL: `http://localhost:8000` in dev (or whatever `NEXT_PUBLIC_API_URL` points at).
- Auth: `Authorization: Bearer <jwt>`, obtained from `POST /auth/login` or `/auth/register`. No cookies, no sessions server-side.
- Every error response has the same shape: `{"error": {"message": "...", "code": <http status>}}`. Validation errors (422) additionally include `"details"` (Pydantic's per-field error list) or, for a few endpoints that collect multiple business-rule violations at once (publish validation, AI question-set validation), a `"message"` that is itself `{"errors": ["...", "..."]}` rather than a plain string.
- Role gating is enforced server-side on every route via FastAPI dependencies (`require_role(...)`), never inferred from the frontend. A wrong role gets `403`; a right role but wrong ownership (someone else's batch, another student's attempt) gets `404` — deliberately, so a student probing random UUIDs can't distinguish "doesn't exist" from "exists but isn't yours."

## Auth

| Method & path | Role | Notes |
|---|---|---|
| `POST /auth/register` | anyone | bcrypt-hashes the password; returns a JWT + the new user |
| `POST /auth/login` | anyone | |
| `GET /auth/me` | any authenticated user | |

## Academic structure

| Method & path | Role | Notes |
|---|---|---|
| `POST/GET /batches` | teacher | list is scoped to the caller's own batches |
| `GET/PATCH /batches/{id}` | teacher, owner | |
| `GET/POST /batches/{id}/students` | teacher, owner | POST creates a new student account (random unrecoverable password — see `docs/development.md`'s deferred items) or attaches an existing one by email |
| `GET/POST /subjects`, `GET/POST /topics` | teacher | global catalog data, not batch-scoped (see `docs/database.md`) |
| `GET /students`, `GET /students/{id}` | teacher (own students only) | |
| `GET /teachers/dashboard` | teacher | real batch/student counts, no hardcoded numbers |

## Homework

| Method & path | Role | Notes |
|---|---|---|
| `POST /homework` (multipart) | teacher | attachments validated (MIME allowlist, size cap, randomized storage filename) |
| `GET /homework`, `GET /homework/{id}` | teacher or enrolled student | students only see homework for batches they're actively in |
| `PATCH /homework/{id}` | teacher, owner | |
| `GET /homework/{id}/attachments/{attachment_id}/file` | teacher or enrolled student | |
| `POST /homework/{id}/submissions` (multipart) | student | rejected after the deadline (`403`) unless the teacher set `allow_late_submissions` |
| `GET /homework/{id}/submissions` | teacher, owner | full roster: submitted/late/pending per student |
| `GET /homework/{id}/submissions/me`, `.../{student_id}` | student (own) / teacher (owner) | a student requesting another student's submission gets `404` |
| `GET .../submissions/{student_id}/file` | same scoping | |

## Assessments

| Method & path | Role | Notes |
|---|---|---|
| `POST/GET /assessments` | teacher (create) / teacher+student (list, scoped) | new assessments start `DRAFT` |
| `GET/PATCH /assessments/{id}` | scoped | students only see `PUBLISHED`/`CLOSED` ones in their batch |
| `POST/GET /assessments/{id}/questions` | teacher, owner | blocked once published |
| `PATCH/DELETE /assessments/{id}/questions/{qid}` | teacher, owner | blocked once published; same edit path for manual and AI-sourced questions |
| `POST /assessments/{id}/publish` | teacher, owner | runs the full validation gate (no empty correct-answer sets, no orphaned options, marks must sum to the declared total) — `422` with every violation listed if it fails |
| `POST /assessments/{id}/close` | teacher, owner | blocks new attempts; existing ones can still be finalized |
| `POST /assessments/{id}/attempts` | student, enrolled | idempotent — resumes an existing attempt rather than creating a second one |
| `GET /attempts/{id}`, `.../responses` | student (own) / teacher (owner) | correct answers withheld while `IN_PROGRESS` |
| `POST /attempts/{id}/responses` | student, owner | autosaves one question at a time; objective types graded immediately server-side; rejected (`403`) once the timer has expired |
| `POST /attempts/{id}/submit` | student, owner | idempotent; auto-triggered by timer expiry too |
| `GET /attempts/{id}/review` | student (own) / teacher (owner) | only once finalized — correct answers revealed |
| `GET /assessments/{id}/attempts` | teacher, owner | roster for grading |
| `PATCH .../attempts/{id}/responses/{qid}/grade` | teacher, owner | subjective questions only (`409` on an objective one — those are never manually scored) |

## Analytics

| Method & path | Role | Notes |
|---|---|---|
| `GET /students/{id}/performance` | self / owning teacher | overall mastery, strengths, weak topics — see `docs/analytics.md` |
| `GET /students/{id}/topics/{tid}/performance` | self / owning teacher | full per-topic breakdown |
| `GET /batches/{id}/attention-panel` | teacher, owner | one row per student: weakest topic + trend |
| `GET /batches/{id}/class-performance` | teacher, owner | average/median/high/low/distribution + per-topic breakdown |
| `GET /assessments/{id}/analytics` | teacher, owner | question-level percent-correct/avg-time |
| `POST/GET /batches/{id}/attendance` | teacher, owner | mark/read one day's roster |
| `GET /students/{id}/attendance` | self / owning teacher | percentage + record history |

## AI (all rate-limited, see `docs/security.md`)

| Method & path | Role | Notes |
|---|---|---|
| `POST /ai/generate-questions` | teacher | forced-JSON generation, validated, lands as a `DRAFT` assessment — **never auto-published** |
| `POST /ai/assessments/{id}/questions/{qid}/regenerate` | teacher, owner | replaces one question in place |
| `POST /ai/pdf-extract` (multipart) | teacher | returns `202` immediately with a job id; extraction runs in the background |
| `GET /ai/jobs/{id}` | teacher, owner | poll for `PENDING/PROCESSING/COMPLETED/FAILED` |
| `GET /ai/students/{id}/topics/{tid}/insight` | self / owning teacher | only the structured profile (mastery/accuracy/trend numbers) reaches the AI, never raw rows; response checked for invented numbers before being returned |

## Personalization

| Method & path | Role | Notes |
|---|---|---|
| `POST /students/{id}/topics/{tid}/practice` | self | `404` if no performance data exists for the topic yet; rejects (`422`) if the AI's difficulty mix doesn't exactly match what was requested |
| `GET /practice-sets/{id}` | owner | correct answers withheld until `COMPLETED` |
| `POST /practice-sets/{id}/responses` | owner | immediate self-grading |
| `POST /practice-sets/{id}/complete` | owner | idempotent; returns before/after mastery with the causation disclaimer attached in the response body itself |

## Pagination, filtering, sorting

Nothing in this API paginates yet — every list endpoint returns its full
result set. At the demo/single-institute scale this project targets (a few
hundred students, a few dozen assessments per batch) that's genuinely fine;
see `docs/development.md`'s "what I'd prioritize next" for when this would
need to change.
