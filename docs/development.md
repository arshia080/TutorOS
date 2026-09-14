# Development

## Local setup

```bash
# 1. Postgres + Redis (optional in dev -- see "Running without Docker" below)
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on mac/linux
pip install -r requirements.txt
copy .env.example .env      # cp on mac/linux
alembic upgrade head
python -m scripts.seed      # optional: realistic demo data, see section below
uvicorn app.main:app --reload --port 8000

# 3. Celery worker (separate terminal) -- required for PDF extraction / analytics
# recalculation jobs to actually run; the API will accept requests and enqueue
# jobs without this, they just won't be processed.
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo   # drop --pool=solo on mac/linux

# 3. Frontend (separate terminal)
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Visit `http://localhost:3000/register`. Interactive API docs are at
`http://localhost:8000/docs` once the backend is running.

### Running without Docker

Every model uses SQLAlchemy's dialect-generic types, so nothing breaks by
pointing `DATABASE_URL` at SQLite instead of Postgres for local dev:

```
DATABASE_URL=sqlite:///./dev.db
```

This is how the project has actually been developed throughout — see
`docs/PROGRESS.md` for why (no working Docker environment was available
during development). Migrations, the ORM layer, and the full test suite all
run unmodified either way; only the connection string changes.

## Seed data

`python -m scripts.seed` (from `backend/`) creates realistic demo data per
product spec §35: 3 teachers, 5 batches, 40 students, 2 subjects (6 topics),
several homework assignments in varied submission states, several
assessments with hundreds of responses across every student, and 15 days of
attendance for everyone. All seeded accounts use password `password123`. The
script is idempotent-by-skip: if `priya.nair@tutoros.dev` already exists it
prints a message and does nothing, so re-running it after a partial failure
is always safe.

Three students in the first Mathematics batch (`Rahul Sharma`, `Ishita
Singh`, `Arjun Mehta`) have hand-crafted score trajectories (mastered/stable,
declining, improving) specifically so the Attention Panel and class charts
show real narrative variety when you look at them — everyone else gets
plausible pseudo-random (but seeded, so reproducible) performance.

## Code layout conventions

See `docs/architecture.md` for the full layering diagram. The short version
for adding a new feature:

1. Model(s) in `app/models/<feature>.py`.
2. `alembic revision --autogenerate -m "..."`, then **read the generated
   file** before running it — autogenerate is a starting point (it gets
   composite constraints and some type details right, but won't infer
   business-logic-driven indexes or catch a renamed column vs. a
   drop-and-add), not something to blindly trust.
3. Pydantic schemas in `app/schemas/<feature>.py`.
4. All business logic + authorization checks in
   `app/services/<feature>_service.py` — routes should never contain a
   SQLAlchemy query or an ownership check directly.
5. Thin route handlers in `app/api/routes/<feature>.py`, registered in
   `app/main.py`.
6. Tests in `tests/test_<feature>.py`, mocking the AI provider
   (`fake_ai_provider` fixture) if the feature touches one — **no test in
   this suite makes a real Anthropic API call**.

## Testing

```bash
cd backend
pytest -q          # full suite
pytest tests/test_assessments.py -q   # one file
```

The suite is organized one file per feature area, mirroring
`app/services/`. Key fixtures (`tests/conftest.py`):

- `client` — a `TestClient` wired to an in-memory SQLite database, reset between tests.
- `db_session` — direct DB access for tests that need to seed data the API can't construct directly (e.g. backdating a timestamp to test timer expiry).
- `fake_ai_provider` — a test double satisfying the `AIProvider` interface; patches both the FastAPI dependency (request-path AI calls) and the module-level lookup background tasks use, so no code path can accidentally reach the real Anthropic API in tests.

`tests/test_demo_flow.py` runs the entire product spec §34 demo flow as one
continuous test (PDF upload → AI extraction (mocked) → publish → student
attempt → performance update → weak-topic detection → practice generation →
completion → analytics update) — proving the phases compose, not just that
each one works in isolation.

## Structured logging

`app/core/logging.py` configures level/format; individual services log at
these points (grep `logger\.` in the relevant service file for exact
call sites):

| Event | Where | Level |
|---|---|---|
| Registration (success / duplicate-rejected) | `auth_service.py` | info |
| Login (success / failed) | `auth_service.py` | info / warning |
| Assessment created / publish rejected / published | `assessment_service.py` | info |
| AI provider request failed | `ai/anthropic_provider.py` | error |
| PDF extraction job completed / failed validation / failed | `ai_pdf_service.py` | info / warning / error |
| Performance recalculation failed | `analytics_service.py` | error |
| Any unhandled exception (500) | `core/errors.py`'s global handler | exception (full traceback) |

No call site logs a password, password hash, or JWT token — see
`docs/security.md`'s logging hygiene section for how this was verified.

## Deployment

No component of this application hard-codes a deployment assumption — every
external dependency is an environment variable or a swappable abstraction
(see `docs/architecture.md`). Frontend, backend, database, object storage,
and Redis are all independently deployable:

- **Frontend**: any Next.js host (Vercel, or a Node server / static export elsewhere). Set `NEXT_PUBLIC_API_URL` to the deployed backend's URL.
- **Backend**: any ASGI host that can run `uvicorn app.main:app` (a container on any platform, a PaaS, a VM). Set `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `ANTHROPIC_API_KEY` (optional), `STORAGE_BACKEND` + storage credentials once a non-local `StorageBackend` implementation exists.
- **PostgreSQL**: any managed Postgres (RDS, Cloud SQL, Neon, etc.) — just a connection string, no schema assumptions beyond what Alembic migrations create.
- **Object storage**: `app/storage/` is an abstraction (`StorageBackend`) with two implementations — `LocalDiskStorage` (default) and `S3Storage` (any S3-compatible endpoint: MinIO in `docker-compose.yml` for dev, real AWS S3/R2 in prod). Set `STORAGE_BACKEND=s3` plus the `S3_*` env vars (see `.env.example`) — the application code calling `get_storage()` doesn't change either way.
- **Redis**: backs real Celery background jobs and the rate limiter (`docker-compose.yml` provisions it; `app/celery_app.py` and `app/core/rate_limit.py` connect to it — see `docs/architecture.md` and `docs/security.md`).

None of frontend/backend/database/storage/Redis need to run on the same host,
the same platform, or even the same cloud provider. In production, run at
least one Celery worker process alongside the API process — jobs enqueue fine
without one, but never execute.

**Concretely**: `render.yaml` at the repo root is a Render Blueprint that
provisions the backend web service, the Celery worker, Postgres, and Redis
in one step (Render → New → Blueprint → point at this repo). The frontend
deploys separately to Vercel (root directory `frontend`, one env var:
`NEXT_PUBLIC_API_URL` pointing at the Render backend's URL). `DATABASE_URL`
accepts a managed provider's raw `postgres://`/`postgresql://` connection
string directly (auto-normalized to the `postgresql+psycopg://` driver form
`app/core/config.py` needs); `CORS_ORIGINS` accepts either the `.env` file's
JSON-array form or a plain comma-separated string, whichever is easier to
paste into a given host's dashboard.

## What's deferred (and why)

- **Real OCR** (`pytesseract`/`pdf2image`): would need system binaries (Tesseract, Poppler) not installed here; the code path is real and would work once they're installed — see `docs/ai-pipeline.md`.
- **Parent role**: explicitly out of scope for the MVP per product spec §3; the `PARENT` enum value exists on `users.role` so adding it later doesn't require a schema migration, just new endpoints/permissions.
- **Pagination**: no list endpoint paginates yet — fine at the scale this project targets (see `docs/api.md`), would need addressing before a much larger institute's data set.
