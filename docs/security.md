# Security

This documents the security posture as of Phase 7's audit, what was found and
fixed during that audit, and what a real production deployment must change
before going live (the defaults here favor a frictionless local dev/demo
experience, not production hardening).

## Password storage

`bcrypt` via `passlib.CryptContext` (`app/core/security.py`), a modern,
purpose-built password hashing algorithm (adaptive cost factor, per-password
salt). Plaintext passwords are never stored, logged, or returned in any API
response — verified by grep across every schema and every `logger.*` call
site (see [§ Logging](#logging-hygiene) below).

## Authentication & sessions

JWT, `HS256`, issued on register/login, no server-side session state. The
`jwt_secret_key` setting **defaults to a clearly-labeled placeholder**
(`"change-me-in-production"`) — this is intentional (a working default for
local dev with zero setup) but is a hard requirement to change before any
real deployment; see `docs/development.md`'s deployment checklist.

## Authorization

Every resource-scoped endpoint enforces ownership **in the service layer**,
not just by hiding UI affordances on the frontend. The pattern used
everywhere: fetch the resource, compare its owning `teacher_id`/`student_id`
against the authenticated user, and return `404` (not `403`) on a mismatch —
so a student or teacher probing another user's resource IDs can't distinguish
"doesn't exist" from "exists but isn't yours." This is tested exhaustively:
every phase's test suite includes at least one teacher-vs-teacher and
student-vs-student isolation test (batches, homework, assessments, attempts,
attendance, practice sets, AI insights).

## Input validation

Every request body is a Pydantic model with explicit types, length limits
(`Field(min_length=..., max_length=...)`), and range constraints
(`Field(gt=0)` on marks/counts/durations, etc.) — structurally invalid input
never reaches a service function. Business-rule validation that Pydantic
can't express (option-shape rules per question type, practice difficulty-mix
enforcement, AI output validation) lives in dedicated, tested modules
(`question_validation.py`, `ai_validation.py`).

## SQL injection

Every database query in this codebase goes through SQLAlchemy's ORM query
builder or parameterized `Session.get()`/`.query()` calls — **zero raw SQL
string interpolation anywhere in `app/`**, confirmed by grep during this
phase's audit (`grep -rn "text(\|execute(\"" app/` — the only matches were
unrelated method names like `.extract_text()` and `generate_text()`).

## File upload validation

Enforced identically on every upload path (homework attachments/submissions
via `app/services/upload_service.py`; PDF extraction via its own check in
`app/api/routes/ai.py`):

- **MIME allowlist** — an unrecognized `content-type` is rejected (`415`) before any bytes are read into memory for storage.
- **Size cap** — `settings.max_upload_size_bytes` (homework, 10MB) / a separate 20MB cap for PDFs; oversized uploads are rejected (`413`).
- **Randomized storage filename** — the client-supplied filename is *never* used as the on-disk path. The storage key is always `uuid4().hex + extension`, where the extension comes from a MIME-to-extension allowlist table, not from the client's filename (which could otherwise smuggle a path or a misleading extension). The original filename is kept only as display metadata in the database.
- **Storage keys are never returned by any API response** — confirmed by grep (`grep -rn "storage_key" app/schemas/` returns nothing). Clients only ever see an opaque attachment/submission ID and download through an authorized proxy endpoint (`GET .../file`), never a direct storage URL.

### Found and fixed during this phase's audit: `Content-Disposition` header injection

The two file-download endpoints (`GET /homework/{id}/attachments/{aid}/file`,
`GET /homework/{id}/submissions/{sid}/file`) interpolated the (lightly
sanitized, but not fully escaped) display filename directly into a
`Content-Disposition` response header. A filename containing a double quote
could break out of the quoted value; more seriously, one containing `\r\n`
could inject additional response headers. Fixed by
`app/services/upload_service.py::content_disposition()`, which strips every
ASCII control character (not just quotes/backslashes) from an ASCII fallback
and separately percent-encodes the full filename per RFC 6266's `filename*`
syntax. Covered by `tests/test_upload_service.py`, including an explicit
CRLF-injection regression test.

## Rate limiting

Applied to every AI-backed endpoint (`app/core/rate_limit.py`): question
generation, question regeneration, PDF extraction, performance insights, and
practice-set generation — `settings.ai_rate_limit_per_minute` (default 10)
requests per user per 60-second window. Exceeding it returns `429` with a
clear message.

**This is a Redis-backed, fixed-window limiter** (`INCR`+`EXPIRE` per
`(bucket, user_id)` key) — correct across multiple worker processes and
instances, since the counter lives in Redis rather than in-process memory.
Live-verified against the real Redis container: 10 requests succeed (or
404, depending on the endpoint's own checks), the 11th returns `429`. The
test suite swaps in an in-memory fake (`tests/conftest.py`) so it needs no
real Redis to run.

## CORS

`CORSMiddleware` is configured with `allow_origins` restricted to
`settings.cors_origins` (defaults to just the frontend's own origin,
`http://localhost:3000`) — never a wildcard, especially not combined with
`allow_credentials=True` (which browsers reject for wildcard origins anyway,
but this codebase doesn't rely on that browser behavior as its only defense).

## Secrets

- No API keys, JWT secrets, or database credentials appear anywhere in source control — confirmed by grep for common key patterns (`sk-`, hardcoded `api_key=`) across both `backend/app/` and `frontend/src/`; both came back clean.
- `.env` (backend) and `.env.local` (frontend) are gitignored by two separate `.gitignore` files (`/.gitignore`'s bare `.env` pattern, and `frontend/.gitignore`'s auto-generated `.env*`) — verified directly with `git check-ignore -v`, not just assumed from the pattern text.
- `.env.example` files document every required variable with placeholder/empty values, never real ones.
- The frontend never embeds a secret — it only ever holds `NEXT_PUBLIC_API_URL`, which is not sensitive (it's the same URL the browser calls directly anyway).

## Logging hygiene

Structured logging exists for every event category the spec names (see
`docs/development.md` for the full list of what logs what). Every logging
call site was reviewed during this phase's audit
(`grep -rn "logger\.(info|warning|error|debug)" app/`) — **no call site logs a
password, password hash, or JWT token**. Auth events log the user's email
(standard audit-log practice, not a secret) and user ID, never credentials.

## What a real deployment must change

None of the following are bugs in this codebase — they're placeholder
defaults appropriate for a zero-setup local demo, listed here explicitly so
they're never mistaken for "already handled":

1. Set a strong, random `JWT_SECRET_KEY` (the default is a labeled placeholder).
2. Set a real `ANTHROPIC_API_KEY` if AI features are wanted (the app runs fine without one; AI endpoints just return a clear `502` until it's set).
3. Point `DATABASE_URL` at managed Postgres, not SQLite.
4. Set `STORAGE_BACKEND=s3` and point it at real S3/R2 (not the local MinIO container) — see `docs/architecture.md`.
5. Set `cors_origins` to the real deployed frontend URL, not `localhost`.
6. Put the app behind HTTPS (TLS termination at a load balancer/reverse proxy — this app itself doesn't terminate TLS).
