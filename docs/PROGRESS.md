# Build Log

## 2026-09-13 — Phase 9: Google Authentication

Adds "Sign in with Google" (OpenID Connect, authorization code flow)
alongside the existing email/password auth from Phase 0, without changing
that flow at all — every existing `POST /auth/login`/`POST /auth/register`
test still passes unchanged, and a regression check against the real running
Postgres-backed dev server confirmed a seeded LOCAL account still logs in
identically after this phase's schema changes.

**The account-matching decision (the highest-risk part of this phase):**
Went with **option (b)** — a Google sign-in whose email matches an existing
LOCAL account (no `google_id` linked yet) is **rejected outright**, never
silently merged, with a message pointing the user at their password and at
account linking from Settings:

```
"An account already exists with this email. Sign in with your password,
 then connect Google from Settings."
```

The reasoning is exactly the risk the prompt named: `email_verified` on a
Google ID token is Google's claim, not a cryptographic proof this specific
human owns the LOCAL account already sitting at that email address in *our*
database. Auto-linking on email match alone means a bug or edge case in
Google's verification (or, more realistically, a LOCAL account registered
with an email the person doesn't currently control — a lapsed domain, a
typo'd signup, a shared/former work email) becomes a silent account
takeover. Rejecting and requiring an *explicit*, *already-authenticated*
linking step closes that gap: `link_google_account()` only ever runs after
the request has already passed through `get_current_user` (a valid existing
session, proven by password login), so linking Google requires proving you
already control the account by a completely different, already-trusted
mechanism. This is why the account-linking capability mentioned as optional
in option (b)'s text was built as a real feature, not left as a promise the
rejection message makes and nothing fulfills — it directly closes the loop.

**Why `google_id` is separate from `auth_provider`** (a deliberate schema
decision beyond the prompt's literal two-column ask): a LOCAL user who links
Google keeps `auth_provider = LOCAL` — that column answers "how was this
account originally created," not "what can it sign in with today."
`google_id IS NOT NULL` is the actual, single source of truth for "can this
account also sign in with Google" (exposed to the frontend as
`UserRead.google_linked`, a computed property, not a stored column). This
means the account-matching logic never has to reason about `auth_provider`
at all when deciding whether a Google login should succeed — it only ever
asks "does a user with this `google_id` exist" and, failing that, "does a
user with this email exist" (collision) or not (new signup). Simpler
invariant, fewer states to get wrong.

**DB (migration `70c55e969973`):** `password_hash` made nullable (a
GOOGLE-only account never sets one — `authenticate_user()` was audited and
fixed to check `password_hash is not None` before ever calling
`verify_password()`, since passlib doesn't handle a `None` hash gracefully);
`auth_provider` enum column (`LOCAL`/`GOOGLE`, default `LOCAL`, backfilling
every pre-existing seeded/created user correctly since Google auth didn't
exist before this phase); `google_id` (nullable, unique, indexed). One real
migration wrinkle hit and fixed here: unlike every prior phase's enum
columns (created together with their table via `op.create_table`, which
auto-creates the Postgres type as a side effect), adding an enum column to
an **existing** table via `op.add_column` doesn't auto-create the type —
`ALTER TABLE users ADD COLUMN auth_provider auth_provider ...` failed with
"type does not exist" until the migration was hand-edited to call
`sa.Enum(...).create(op.get_bind(), checkfirst=True)` first, with a matching
`.drop()` in `downgrade()`. Also hand-added a `server_default='LOCAL'` on
the `ADD COLUMN` step (Postgres requires one when adding a `NOT NULL`
column to a non-empty table) and dropped the default immediately after, so
the column definition matches the model exactly (new rows get their default
from `app/models/user.py`, not from the database).

**Backend (`app/services/google_oauth_service.py`, `app/services/auth_service.py`,
`app/api/routes/auth.py`):**
- Three signed, short-lived JWTs (reusing the app's existing `jwt_secret_key`
  and `jose` signing infra — "the app's own JWT issuance," just for
  different purposes than a session token) do all the trust-boundary work:
  the CSRF `state` parameter (`purpose: google_login` or `google_link`,
  10-minute expiry), the pending-signup token (issued only *after* a real
  Google ID token has already been verified server-side, carrying the
  verified `sub`/`email`/`name` so the frontend's role choice is the only
  thing `POST /auth/google/complete-signup` has to trust from the client),
  and nothing else needs its own crypto.
- `GET /auth/google/login` builds the Google consent URL (`scope=openid
  email profile`, `state=<signed nonce>`) and redirects immediately — this
  one really can be a bare redirect since it's reached by a browser with no
  session yet.
- `GET /auth/google/callback`: **CSRF check first, before anything else** —
  `decode_state()` rejects a forged, tampered, or expired `state` and the
  function returns immediately; the code exchange and ID-token verification
  literally cannot run without a valid state. Then: exchange code for
  tokens server-to-server (`httpx.post` to Google's token endpoint — the
  frontend never sees a Google ID token at all in this flow), verify the ID
  token's **signature** against Google's live JWKS (`jose.jwt.decode` with
  the matching JWK by `kid`, `algorithms=["RS256"]`, `audience=` the app's
  own client id) plus `iss` checked against both of Google's two valid
  issuer strings (`accounts.google.com` / `https://accounts.google.com` —
  `jose` only accepts one issuer value per call, so this one check is done
  manually after decode). `email_verified: false` is rejected outright,
  before any account lookup happens — no user is created or touched.
- `GET /auth/google/link` is **not** a redirect (a plain browser navigation
  can't carry the `Authorization` header this authenticated endpoint needs)
  — it's a normal authenticated JSON endpoint returning
  `{authorization_url}`, which the frontend then navigates to itself with
  `window.location.href`. This is the one place the OAuth flow's "redirect
  vs JSON" shape had to bend around an already-logged-in caller.
- `find_user_for_google_login()` is the single function the account-matching
  decision lives in: lookup by `google_id` → login; else lookup by `email`
  → raise `GoogleLoginCollision` (never silently merge); else `None` → the
  route redirects to `/auth/google/choose-role?token=<pending>` instead of
  creating a user with a guessed role.
- `POST /auth/google/complete-signup` re-validates for a race (two tabs
  completing signup, or a LOCAL account registered with that email in the
  10-minute window) rather than trusting the pending token's freshness
  alone, and its `role` field is a `Literal["TEACHER","STUDENT","PARENT"]`
  — deliberately narrower than the existing `POST /auth/register`, which
  still accepts any `UserRole` including `ADMIN` (a pre-existing gap from
  Phase 0, unrelated to this phase and not touched here, but worth not
  making *worse* on a new public endpoint).
- `rate_limit_by_ip()` (new function in `app/core/rate_limit.py`, alongside
  the existing per-user `rate_limit()`) applied to `/auth/google/callback` —
  this endpoint is reached by an anonymous browser mid-redirect, so it has
  no authenticated user to key a rate limit on yet; keyed by
  `request.client.host` instead, same Redis `INCR`+`EXPIRE` mechanism.
  Worth noting: **no other auth endpoint in this codebase has rate limiting
  today** (checked before writing this — `/auth/login`/`/auth/register`
  have none), so "like other auth endpoints" mostly meant "reuse the
  existing rate-limiting *pattern*," not an existing sibling; this phase
  doesn't retroactively add it to the password endpoints since that's a
  separate, unscoped decision about brute-force protection.
- `.env.example` gained `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/
  `GOOGLE_REDIRECT_URI`/`FRONTEND_URL` with placeholder values (the client
  id/secret are `None` by default — Google auth endpoints return a clean
  `google_not_configured` redirect rather than crashing on boot, same
  pattern as `anthropic_api_key`).

**Tests (11 new, 160 total, all passing):** new-user signup through the
pending-token → role-selection → account-creation path (and that no user
row exists in the gap between them); a first-time signup rejected from
self-selecting `ADMIN` (422, since the schema itself excludes it); login for
an existing GOOGLE-provider user; `email_verified: false` rejected with zero
account creation; the LOCAL/GOOGLE email collision explicitly asserting the
LOCAL account's `google_id` stays `None` afterward (never auto-linked); the
full explicit-linking flow (link → same Google identity now logs into the
*same* account) and its email-mismatch rejection; three separate CSRF
cases — a completely forged state, a missing state, and a correctly-signed
but expired state — each asserted to redirect with `error=invalid_state`
*and* (for the forged case) that `exchange_code_for_id_token` was never even
called, proving the CSRF check genuinely gates the network call rather than
just happening to also fail later; and a same-role-both-ways check that a
Google-issued JWT and a password-issued JWT produce identical results
(`201`/`200`) against the same teacher-only endpoints. Every test that
stands in for "a real Google login happened" does so by monkeypatching
`google_oauth_service.exchange_code_for_id_token`/`.verify_id_token`
directly (the same test-double-via-module-monkeypatch pattern this codebase
already uses for `db_session_module.SessionLocal` and the AI provider) —
the state-signing and JWT-decoding logic itself is never mocked, only the
two functions that would otherwise talk to Google's real servers.

**Frontend:** a `GoogleSignInButton` component following Google's official
branding guidelines (the real multicolor "G" mark, specified border color
`#747775`, white background — not a custom lookalike) added to both
`/login` and `/register`; `/login` also reads `?error=<code>` and maps every
backend error code to a specific human-readable message (not a generic
"something went wrong"). `/auth/google/complete` reads the JWT from the URL
**fragment** (`#token=...`, deliberately not a query param — fragments are
never sent to any server and never appear in Referer headers, unlike query
strings) and stores it exactly like a password login would. `/auth/google/choose-role`
reads the pending-signup token from the query string (fine there — it's
short-lived and single-use, not a session credential) and posts the chosen
role to `complete-signup`. New `/dashboard/settings` page (didn't exist
before this phase) with a "Connect Google account" action for LOCAL users
without `google_linked`, calling the authenticated `GET /auth/google/link`
and then navigating the browser to the URL it returns.

**Decisions:**
- No student-approval-style alternative was considered for the collision
  case (only option (b), never option (a)'s "confirm via password inline
  during the Google flow itself") — (b) needed no new UI surface mid-OAuth-
  redirect, just a message and a link to a place that already needed to
  exist (Settings).
- `password_hash` is nullable now, but `RegisterRequest`'s password field is
  still required and unchanged — a LOCAL account always has a password; only
  a GOOGLE-created account can have `password_hash IS NULL`. Nothing in this
  phase makes password login optional for anyone who already has one.
- The pending-signup and state JWTs share the main session-token signing key
  (`settings.jwt_secret_key`) rather than a separate secret — they're
  already short-lived, single-purpose, and distinguished by a `purpose`
  claim checked on every decode; a second secret would be additional
  configuration surface for no real isolation benefit at this scale.

**Verified:**
- `pytest` — 160/160 passing (149 prior + 11 new).
- `npm run build` — succeeds; all 4 new routes (`/auth/google/complete`,
  `/auth/google/choose-role`, `/dashboard/settings`, plus the extended
  login/register pages) compile and type-check cleanly, including the
  `useSearchParams()` + `Suspense` boundary Next.js requires for pages that
  read query params on a client component (missing this fails the build,
  not just a runtime warning — caught and fixed here).
- **Live-verified against the real running dev server** everything that
  doesn't require an actual registered Google OAuth client or a real Google
  account (neither exists in this environment, same category of limitation
  as every other external-service phase — the Anthropic API key, real S3,
  etc.): `GET /auth/google/login` with no client id configured redirects
  cleanly to `.../login?error=google_not_configured` instead of crashing;
  existing seeded LOCAL accounts (`priya.nair@tutoros.dev`) still log in and
  register normally post-migration, with the response now correctly
  including `auth_provider: "LOCAL"` and `google_linked: false`; a forged
  `state` on `/auth/google/callback` redirects with `error=invalid_state`
  rather than crashing or proceeding; and `build_authorization_url()`
  produces a well-formed Google consent URL (verified directly, including a
  correctly round-tripping signed `state`) once fake credentials are set.
  The frontend dev server was confirmed serving all new pages, and the
  Google button renders on both `/login` and `/register`.
- **Not verified**: an actual end-to-end login with a real Google test
  account through a real browser, for any of the three roles — this
  environment has no browser and no registered Google Cloud OAuth client.
  Everything up to and including real-Google-server communication (the
  code-exchange and JWKS-signature-verification *logic*) is implemented and
  covered by the mocked test suite; only "does Google's real consent screen
  and token endpoint actually behave the way its documentation says" is
  unverified, which is exactly the boundary `google_oauth_service`'s two
  network-calling functions exist to isolate. **Before this goes near
  production**: register a real OAuth 2.0 Client ID in the Google Cloud
  Console, set the real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/
  `GOOGLE_REDIRECT_URI` in a real `.env`, and click through the full flow at
  least once per role (new signup, existing-Google login, LOCAL-collision
  rejection, and account linking from Settings) in an actual browser.

**This phase stops here for review before any of it goes near production**,
per the explicit instruction.

## 2026-09-13 — Phase 8: Parent Portal (extends beyond original MVP scope)

The original spec (§3) explicitly deferred the PARENT role but designed the
schema (`UserRole.PARENT` already existed) so it could be added later without
a rewrite. This phase adds it properly: registration, a verified parent-child
linking flow, teacher discovery by locality, and an aggregated parent
dashboard (mastery, syllabus completion, recent tests, teacher remarks).

**Verification-flow decision (the highest-risk part of this phase):**
Two linking paths were built, both ending at the same `parent_student_links`
row, per the prompt's "either (a) or (b)" — both were implemented since the
frontend spec explicitly asks for both actions ("Enter invite code" / "Request
to connect"):
1. **Invite code** (`link_invite_codes`, `created_by` always a teacher):
   a teacher generates a one-time 8-character code scoped to one student
   (`POST /teachers/students/{id}/invite-code`); a parent entering a
   still-valid, unused code is linked with `status=APPROVED` **immediately** —
   generating and handing over the code IS the teacher's approval, so a second
   approval step would be pure friction with no added safety. Codes expire
   after `settings.link_invite_code_expiry_hours` (default 24h) and can't be
   reused once redeemed (`used_at` set).
2. **Pending request** (no code): a parent who only knows the child's account
   email submits it; this creates a `status=PENDING` row that a teacher who
   actually teaches that student (verified via a real `BatchStudent`/`Batch`
   join, not a trusted client-supplied flag) must explicitly approve or
   reject via `GET/POST /teachers/link-requests`. Chose teacher-only approval
   (not "or student" from the prompt's alternative) to keep the authorization
   surface to one well-tested check rather than two; a student-approval path
   would be a small, isolated addition later if needed.

**The one authorization choke point**: `parent_service.get_approved_link()` —
every single read of a child's data (`GET /parents/children/{id}/progress`)
calls this first, and it only returns a link where `status == APPROVED`
*for that specific parent*. A PENDING or REJECTED link, or no link at all,
raises the same 404 "Child not found" a real stranger would get — never a
403, so a request can't be used to confirm a given student id/email exists
at all, following the same "404 not 403 to avoid resource enumeration"
convention every other phase in this codebase already uses.

**DB (migration `06316e98fd73`):** `parent_profiles`, `parent_student_links`
(unique on `(parent_id, student_id)` — re-requesting after a REJECTED link
updates the same row back to PENDING rather than erroring), `link_invite_codes`,
`syllabus_progress` (unique on `(batch_id, subject_id, topic_id)`), `remarks`;
plus `locality`/`city`/`pincode` added to the existing (previously-unpopulated)
`teacher_profiles` table.

**Backend:**
- `RegisterRequest` gained optional `phone`/`locality` fields (ignored unless
  `role == PARENT`); `register_user()` now also creates a `ParentProfile` row
  for parent signups — the same "profile row created at registration" gap
  that already existed for `TeacherProfile` is *not* fixed here (out of
  scope for this phase; teachers now self-serve their own profile instead
  via the new `PATCH /teachers/profile`, which was the actually-needed fix
  for search to have any real data).
- `app/services/parent_service.py` — the module docstring has the full flow
  writeup above. `list_pending_requests_for_teacher()` filters PENDING links
  down to only students the calling teacher actually teaches, so a teacher
  never sees (or can act on) another teacher's parent requests — verified by
  `test_teacher_cannot_approve_another_teachers_link_request`, which also
  checks the *listing* itself, not just the approve endpoint.
- `app/services/teacher_search_service.py` — `GET /teachers/search` needs no
  auth at all (parents browsing don't need an account yet) and only ever
  touches `teacher_profiles` + aggregate "which subjects/grades has this
  teacher run assessments/batches for" facts, computed the same way analytics
  already aggregates class data — never returns batch, assessment, or student
  identifiers. `subjects_taught` is derived from distinct `Assessment.subject_id`
  per teacher (subjects are a global catalog, not owned by a teacher, so this
  was the only honest way to answer "what does this teacher teach" without a
  new schema field); `grades_taught` from distinct `Batch.grade`.
- `app/services/syllabus_service.py` — `mark_topic()` requires the batch to be
  the teacher's own (reuses `batch_service.get_owned_batch`, same 404-not-403
  pattern) and the topic to actually belong to the given subject; upserts one
  row per `(batch, subject, topic)`. `list_syllabus()` returns every topic in
  the subject with `NOT_STARTED` as the default for topics with no row yet,
  so the checklist UI never has to special-case "untouched."
- `app/services/remark_service.py` — `create_remark()` checks **both** that
  the batch is the teacher's own AND that the student is enrolled in one of
  the teacher's batches (via `student_service.get_student_for_teacher`) —
  two separate ownership facts, not one, since a batch being the teacher's
  doesn't by itself prove this particular student belongs to it.
- Parent progress aggregation (`get_child_progress`) explicitly **reuses**
  Phase 4's `analytics_service.compute_student_performance()` rather than
  reimplementing mastery — converted from its dataclass return via
  `StudentPerformanceRead.model_validate(performance, from_attributes=True)`
  since this is a direct service-to-service call (not a FastAPI response
  return), which is the one place in this call path that needed the explicit
  `from_attributes=True` FastAPI's own response-model machinery normally
  supplies for free.
- Syllabus completion percentage = completed `syllabus_progress` rows for a
  subject within the child's active batch(es) ÷ total `Topic` rows that exist
  for that subject (topics are global, not batch-scoped) — a subject only
  appears in a parent's view once a teacher has touched at least one of its
  topics for that batch, so an untouched subject doesn't show as a
  misleading 0%.
- Routes: `app/api/routes/parents.py` (`POST /parents/link-requests`,
  `GET /parents/children`, `GET /parents/children/{id}/progress`), new
  endpoints on `app/api/routes/teachers.py` (`GET /teachers/search`,
  `GET/PATCH /teachers/profile`, `GET /teachers/link-requests`,
  `POST /teachers/link-requests/{id}/approve|reject`,
  `POST /teachers/students/{id}/invite-code`), new
  `app/api/routes/syllabus.py` (`POST /syllabus/{topic_id}/mark-complete`,
  `GET /batches/{id}/subjects/{id}/syllabus` — the second wasn't in the
  prompt's literal endpoint list but is necessary for the requested "syllabus
  checklist UI" to have anything to render, same category of addition as
  every prior phase's "the spec's UI ask implies an endpoint it didn't name"),
  and two additions to `app/api/routes/students.py`
  (`POST/GET /students/{id}/remarks` — GET wasn't literally requested either,
  needed so the remarks form has a history to show against).

**Tests (16 new, 149 total, all passing):** full link lifecycle both ways
(invite-code instant approval, pending request → approve, pending request →
reject with the rejected child's data never becoming visible), invite-code
reuse rejected, invalid-code rejected, duplicate-pending-request rejected,
unknown-email-request 404s, syllabus completion percentage hand-verified
(1 of 4 topics complete → exactly 25.0%), teacher search filtering by
locality/subject with an exact assertion on the response's field set (proving
no extra/leaked fields), and every authorization "should fail" case named in
the prompt as an explicit test expecting 403/404 rather than an incidental
assertion: parent cannot reach a second child's progress by ID-guessing
despite having a real approved link to a *different* child; a teacher cannot
approve/reject another teacher's link request (and it doesn't even appear in
that teacher's pending list); a teacher cannot mark syllabus progress for
another teacher's batch; a teacher cannot add a remark for a student not in
their own batch; a parent gets 403 attempting either teacher-only action;
and a remark with `visible_to_parent=false` is confirmed absent from the
parent's feed while still present in the teacher's own view of the same
student.

**Frontend:** parent role added to the register form (with conditional
phone/locality fields); dashboard nav branches for `PARENT` (My Children,
Find a Teacher) alongside the existing TEACHER/STUDENT branches; a
`ParentOverview` on `/dashboard` listing linked children as cards (or an
empty state prompting to link one) with a combined "enter code" / "request
by email" form; `/dashboard/children/[id]` for the per-child aggregated view
(mastery list reusing the same `TrendArrow` component the student/teacher
dashboards already use, syllabus progress bars, a recent-tests table, a
remarks feed); `/dashboard/find-teacher` (locality/subject/grade filters,
result cards) — reachable without a completed child-link, matching "parents
can search for tutors near them independent of any existing child link."
**Frontend interpretation note**: the prompt's "Request to connect" action on
a teacher search result implies a per-teacher connection request, but the
backend (correctly, per its own explicit spec) only supports a parent→student
link, not a parent→teacher one — there is no such thing as a "connect to this
teacher" request in the data model. Rather than invent an unspecified
backend capability, the search page's copy points parents to the existing
"Link a child" flow (code or student email) instead of attaching a
non-functional per-card button; documented here rather than silently doing
something different from what was asked.
Teacher-side additions: a "Parent link requests" panel on the teacher's
`/dashboard` overview (approve/reject inline); a `/dashboard/students/[id]`
page (new — students had no detail page before this phase) with the invite-code
generator and a remarks list + add-remark form (category + visible-to-parent
checkbox); `/dashboard/batches/[id]/syllabus` (subject picker + per-topic
status dropdown, showing the live completed/total count).

**Decisions:**
- `ParentStudentLink.relationship` is a plain nullable string column, not an
  enum — the prompt's own examples ("Father", "Mother", "Guardian") read as
  suggestions, not an exhaustive real-world list (step-parents, grandparents
  raising a child, etc.), and free text costs nothing here since it's display
  metadata, not something queried on.
- No student-side approval path was built (only teacher-side), even though
  the prompt offered it as an alternative — see the verification-flow
  decision above.
- `teacher_profiles` rows are still not created automatically for teachers
  (pre-existing gap, unrelated to this phase) — a teacher must visit their
  profile settings and save once before they're discoverable in search. Not
  fixed here since Phase 8's actual ask was the search capability, not
  retroactively backfilling every existing teacher's profile.
- Reseeded `dev.db`'s Postgres tables from scratch (`TRUNCATE ... RESTART
  IDENTITY CASCADE` on every app table, then `python -m scripts.seed`) rather
  than writing a migration-time backfill, since seed data is regenerated
  wholesale on every phase anyway. New seed data: one searchable teacher
  profile (Priya Nair, "Nair Learning Center", Andheri West, Mumbai), 3
  topics of syllabus progress on batch 0 (2 completed, 1 in progress),
  3 remarks on Rahul Sharma (2 visible to parents, 1 deliberately not, to
  demo the filter immediately), one fully APPROVED parent link (Sunita
  Sharma → Rahul Sharma, via the invite-code flow) and one PENDING link
  (Rajesh Singh → a batch-0 storyline student) so the teacher's Link
  Requests panel has something to act on out of the box.

**Verified:**
- `pytest` — 149/149 passing (133 prior + 16 new).
- `npm run build` — succeeds; all 6 new routes (`/dashboard/find-teacher`,
  `/dashboard/children/[id]`, `/dashboard/students/[id]`,
  `/dashboard/batches/[id]/syllabus`, plus the extended register/dashboard
  pages) compile and type-check cleanly on the first pass.
- **Live-verified against the real running dev server and Postgres** (not
  just the test suite): registered a real parent and teacher over HTTP,
  created a batch+student, generated a real invite code, redeemed it as the
  parent (got `status: APPROVED` back immediately), confirmed `GET
  /parents/children` and `GET /parents/children/{id}/progress` both return
  real data over HTTP; separately updated a teacher's profile via `PATCH
  /teachers/profile` and confirmed `GET /teachers/search?locality=...`
  finds it with no auth token at all. All live-test users/batches deleted
  afterward via direct SQL cleanup to keep the dev database matching the
  seed script's baseline. Then fully reseeded and re-verified the *seeded*
  Phase 8 data specifically: `sunita.sharma@tutoros.dev` (password
  `password123`) sees Rahul's real Phase-4-computed mastery numbers
  (`overall_mastery: 74.86`, matching the existing storyline data
  unchanged), his 66.67% Mathematics syllabus completion (2 of 3 topics),
  and exactly 2 of his 3 remarks (the `visible_to_parent=false` one
  correctly absent); `priya.nair@tutoros.dev` sees the pending Rajesh Singh
  request on her dashboard and finds herself via `/teachers/search?locality=Andheri`.
- One real environment issue hit and fixed **during** this phase's live
  verification, unrelated to the code itself: `uvicorn --reload`'s
  WatchFiles-based reloader left orphaned `multiprocessing.spawn` child
  processes holding the listening socket after several restarts on this
  Windows machine, so curl kept hitting a stale pre-Phase-8 process despite
  every log line claiming a clean reload. Diagnosed by comparing a direct
  `python -c "from app.main import app; print(len(app.routes))"` (correct,
  80 routes) against the live server's `/openapi.json` (stale, 47 routes);
  fixed by killing every orphaned `python.exe` process and restarting
  **without** `--reload` for the rest of this session's verification.
- Not yet exercised in a real browser (no headless browser in this
  environment, consistent with every prior phase) — the parent dashboard's
  card layout, the syllabus checklist's dropdown-per-topic UI, and the
  search page's result cards are implemented and API-verified but not
  visually confirmed.

**This phase stops here for review before any of it goes near a real
deployment**, per the explicit instruction — no further phases were started.

## 2026-09-12 — Post-Phase-7: Docker unblocked, real Celery/Redis/S3

Docker Desktop, previously broken across this project's entire development
history, started working in this environment. That unblocked three items
that Phases 0-7 had deferred purely for lack of infrastructure to build or
test against — no design was wrong, only unbuildable. Migrated the running
dev backend from SQLite to real Postgres first (`alembic upgrade head`, fresh
seed, verified real computed analytics over curl) as a prerequisite.

- **Real Celery + Redis** (`app/celery_app.py`): replaced every
  `background_tasks.add_task(fn, ...)` call site with `fn.delay(...)` on a
  `@celery_app.task`-wrapped version of the same function — no service-layer
  logic changed, exactly as the Phase 7 docs predicted. `tests/conftest.py`
  runs Celery in eager mode (`task_always_eager=True`) so the 133-test suite
  needs no real broker. Beyond the test suite, live-verified against a real
  worker process (`celery -A app.celery_app worker --pool=solo`) and the real
  Redis container: dispatched a genuine PDF-extraction job over HTTP, watched
  it flow through Redis into the separate worker process and complete —
  something the eager-mode tests alone can't prove.
- **Real S3-compatible storage** (`app/storage/s3.py`): added `S3Storage`
  satisfying the existing `StorageBackend` interface, using `boto3` against
  any S3-compatible endpoint — a MinIO container (`quay.io/minio/minio`;
  Docker Hub's `minio/minio` repo is gone) added to `docker-compose.yml` for
  dev, or real AWS S3/R2 in prod by leaving `S3_ENDPOINT_URL` unset. Selected
  via `STORAGE_BACKEND=s3`; local disk stays the default. Live-verified
  save/read/delete against the real MinIO container, including the
  correct exception on a deleted key.
- **Redis-backed rate limiting** (`app/core/rate_limit.py`): swapped the
  module-level dict for a real `INCR`+`EXPIRE` fixed-window counter in Redis,
  correct across multiple worker processes/instances (the old dict wasn't).
  `tests/conftest.py` swaps in an in-memory `FakeRedis` test double so the
  suite still needs no real Redis. Live-verified against the real Redis
  container: 10 requests through, the 11th returns a real `429`.
- Updated `docs/architecture.md`, `docs/development.md`, `docs/security.md`,
  and `README.md` throughout to describe these as real/live rather than
  deferred, and removed them from every "what's deferred" list.
- **Still deferred** (no infrastructure gap, just scope): pagination on list
  endpoints, parent role endpoints, student invite/credential-delivery flow,
  rubric-based subjective grading. See "What was deliberately deferred" below
  for the full original reasoning on each.

## 2026-09-12 — Phase 7: Production hardening (final phase)

**Testing:**
- Audited section 30's checklist against the existing suite (auth, authorization isolation, assessment lifecycle, homework deadlines, analytics correctness, AI mocking, PDF pipeline) — all already covered exhaustively by Phases 0-6's own test suites. The one real gap: no test exercised the section 34 demo flow as **one continuous story**. Added `tests/test_demo_flow.py` — teacher creates batch/subject/topics → uploads a real PDF (AI extraction mocked, but the actual `pypdf` text extraction and validation gate run for real) → publishes → student attempts and gets graded → performance updates → Attention Panel surfaces the weak topic → practice generated (mocked) and completed → mastery before/after with the disclaimer, all as one test proving the phases actually compose, not just that each works in isolation.
- Also added `tests/test_rate_limit.py` (2 tests) and `tests/test_upload_service.py` (4 tests, including a genuine security regression test — see below). **133 tests total, all passing, zero real external API calls.**

**Security pass — findings and fixes:**
- **Found and fixed a real vulnerability**: the two homework file-download endpoints interpolated the (only lightly sanitized) display filename directly into the `Content-Disposition` header — a filename containing a quote or CRLF could inject headers. Fixed with `upload_service.py::content_disposition()` (RFC 6266-compliant, strips every control character from the ASCII fallback, percent-encodes the full name), with a dedicated CRLF-injection regression test.
- **Added rate limiting** (`app/core/rate_limit.py`) on every AI-backed endpoint (generation, regeneration, PDF extraction, insights, practice generation) — this was genuinely missing before this phase. In-memory, per-user, per-process (documented limitation — no working Redis in this environment to build/test a distributed version against; the upgrade path is one function). **Caught and fixed a real bug while building this**: the rate limit value was captured as a plain function argument at route-registration time, so `monkeypatch.setattr(settings, ...)` in tests had no effect — the limit must be read from `settings` *inside* the dependency function on every call, not baked into a closure at import time.
- Audited and confirmed clean: password hashing (bcrypt), CORS (restricted origin, never wildcard+credentials), zero raw SQL anywhere in `app/` (grep-verified), file upload validation (MIME allowlist + size cap + randomized storage filename on every upload path), storage keys never present in any API schema (grep-verified), no secrets in source control (both `.env` files independently confirmed gitignored via `git check-ignore -v`, not just assumed from the pattern text), no hardcoded frontend secrets.
- Added structured logging for every event category the spec names (auth register/login success+failure, assessment create/publish/publish-rejected, AI provider failures, PDF job completed/failed-validation/failed, background analytics-recalculation failures) — audited every `logger.*` call site afterward and confirmed none logs a password, hash, or token (emails are logged for auth audit trails, which is standard practice, not a leak).

**Data seeding — substantially rewritten for section 35 compliance:**
- Previous seed data (2 teachers, 3 batches, 15 students, 1 subject, ~20 responses) fell well short of section 35's explicit targets. Rewrote to: **3 teachers, 5 batches, 40 students, 2 subjects (Mathematics + Science, 6 topics total), 485 assessment responses, 600 attendance records** (15 days × 40 students), plus the existing hand-crafted three-student storyline (mastered/stable, declining, improving trajectories) preserved for narrative demo value. The bulk of the new data comes from `_bulk_quiz_rounds()`: a seeded (`random.Random(20260908)`, reproducible) per-student-per-topic aptitude generator with round-to-round drift, so trends emerge organically across the whole class rather than being hand-authored one student at a time.
- Verified with a direct integrity check before touching `dev.db`: zero orphaned foreign keys, all 40 students have at least one attempt, row counts confirmed against every relevant table.

**Documentation — all six new docs, plus the top-level README:**
- `docs/architecture.md` — layering, the four provider/backend abstractions, why `BackgroundTasks` not Celery, why no microservices, both pipeline diagrams.
- `docs/database.md` — every entity group, all 7 migrations, the one deliberate schema deviation from the spec (`response_selected_options`), why SQLite in dev.
- `docs/api.md` — full endpoint reference by feature area, generated by cross-checking the live `/openapi.json` for accuracy rather than hand-transcribing from memory.
- `docs/security.md` — the full audit above, plus an explicit "what a real deployment must change" checklist (JWT secret, API key, managed Postgres, real object storage, Redis-backed rate limiting, real CORS origin, TLS).
- `docs/development.md` — setup, seeding, testing conventions, the full structured-logging table, and the deployment section (frontend/backend/Postgres/storage/Redis are all independently deployable; verified by re-checking every settings field is environment-driven, nothing hardcoded).
- `README.md` — project overview, problem statement, features, architecture diagram, stack table, doc index, setup, engineering-decisions rationale (Postgres/FastAPI/Next.js/BackgroundTasks/topic-level-analytics/documented-mastery-model, each with its actual reason), and "what I'd prioritize next."

**Process note:** `docs/ai-pipeline.md` and `docs/analytics.md` already existed from Phases 5 and 4 — not rewritten, only cross-referenced from the new docs.

**Verified:**
- `pytest` — 133/133 passing.
- `npm run build` — succeeds, all 13 routes compile and type-check cleanly.
- **Full section 34 demo flow walked through live against the real running server** (not just the automated test): fresh teacher creates a batch/subject/topic, publishes two assessments, a fresh student answers one correctly (100% mastery, no weak topic — confirming the pipeline doesn't manufacture a false weak topic) and one incorrectly (mastery drops to 45%, correctly appears on the Attention Panel), practice generation confirmed to gracefully 502 without an API key, then completed live via the same direct-DB-seed-bypass pattern established in Phases 5-6 — mastery moved 45% → 85% with the causation disclaimer attached, exactly as designed. All demo/test data deleted afterward and `dev.db` fully reset+reseeded to confirm a completely clean state (verified: exact expected row counts, zero leftover demo users).

**What was deliberately deferred** (carried from earlier phases, restated here since this is the final phase):
- **Parent role** (spec §3) — the `UserRole.PARENT` enum value exists so no schema migration is needed to add it, but no parent-facing endpoints or UI were built; explicitly out of MVP scope per the spec itself.
- **Real Celery/RQ** and **real OCR** — both need infrastructure (working Docker/Redis, Tesseract/Poppler binaries) never available in this development environment across all 7 phases. Both have real, working code at the seam (`BackgroundTasks` call sites; the OCR fallback function) ready to swap in.
- **Redis-backed rate limiting** and **real S3/R2 object storage** — same story; the abstractions exist, only the swappable implementation is missing.
- **Pagination** on any list endpoint — untested need at this project's target scale (a single institute, a few hundred students).
- **A student invite/credential-delivery flow** — a teacher-created student account currently gets a random, unrecoverable password (documented since Phase 1); a real deployment needs an invite-link or teacher-set-temporary-password flow.
- **Partial credit / rubric-based subjective grading** — one score per subjective response today; fine for a solo tutor, would need standardization for a multi-teacher institute.

## 2026-09-12 — Phase 6: Personalization

**Built:**
- DB: `practice_sets`, `practice_questions`, `practice_question_options`, `practice_responses`, `recommendations` (migration `038ae11f1e8f`). `practice_question_options`/`practice_responses` aren't in the spec's literal table list — necessary because a practice question needs a stored correct answer to be instantly self-gradable (the whole point of practice), and a response needs somewhere to live; same category of addition as every prior phase's schema extensions (documented each time). `practice_responses` has `UniqueConstraint(practice_set_id, practice_question_id)` (resubmitting a question overwrites, doesn't duplicate).
- Weak-topic detection is **not a new calculation** — `compute_topic_performance(...).mastery_score < settings.weak_topic_mastery_threshold` (new config field, default 60, matching the existing "Needs Improvement"/"Critical" band boundary). The magic `60`/`75` literals in Phase 4's `compute_student_performance` were already there; this phase moved the weak-topic one into `Settings` as explicitly instructed ("configurable threshold") and re-ran Phase 4's full test suite unchanged to confirm the refactor was safe.
- "Generate Practice" (`POST /students/{id}/topics/{topic_id}/practice`): reuses the Phase 5 AI provider + the exact same two-layer validation gate (`ai_validation.validate_generated_question_set`) question generation uses, then adds a **third check specific to practice**: the returned questions' difficulty counts must match the requested easy/medium/hard mix *exactly* (default 5/3/2 per the spec's own example, each configurable via `Settings` and overridable per request) — mismatched counts are rejected with a clear per-band error, not silently accepted. Restricted to single-answer question types (MCQ/TRUE_FALSE/NUMERICAL) — see the `ponytail:` comment on `PRACTICE_QUESTION_TYPES` in `app/models/practice.py`.
- Student completion flow: `GET /practice-sets/{id}` (questions, correct answers hidden while `IN_PROGRESS`, revealed once `COMPLETED` — same withholding pattern as Phase 3's assessment attempts), `POST /practice-sets/{id}/responses` (immediate self-grading, one row per question, resubmission overwrites), `POST /practice-sets/{id}/complete` (idempotent — completing an already-completed set just returns the stored result rather than recomputing, verified by `test_completing_twice_is_idempotent`).
- **Before/after mastery is deliberately NOT a call to Phase 4's `compute_topic_performance()`** — practice responses are never joined into that function's query, on purpose: if they were, a student could inflate their real exam-based mastery (the number teachers see on the Attention Panel) just by grinding easy self-generated practice questions, which that formula was never designed to guard against. Instead `mastery_after` reuses the *exact same weighted formula and weights* but scopes `recent_accuracy` to the practice set's own accuracy and shifts the topic's previous `recent_accuracy` into the "historical" slot — a new, formula-grounded number that's honestly about "how did you do on this practice set," not a silent rewrite of the real mastery figure. Full methodology + worked reasoning added to `docs/analytics.md`.
- **Every before/after result is explicitly labeled** — `PracticeCompletionRead.note` carries "this is an observed change... not proof that the practice caused it" in the API response itself (not just documentation), and the frontend result screen surfaces that sentence directly under the before/after numbers, per the phase's explicit instruction.
- A `Recommendation` row is created alongside every generated practice set (`status=PENDING`, `priority` = the mastery gap below the weak-topic threshold, rounded) and flipped to `COMPLETED` when the practice set finishes — gives the `recommendations` table real, used data rather than being an inert schema requirement.
- Tests: 11 new (126 total, all passing). Weak-topic threshold logic (above/at/below the configurable boundary); practice generation respecting the requested difficulty mix exactly, and rejecting both a wrong mix and a disallowed question type (MULTI_SELECT); the full generate → answer → complete flow with real before/after mastery numbers; completion rejected with no answers; completion idempotency; authorization (a student can't generate practice for another student, can't open another student's practice set).
- Frontend: the student dashboard's existing "Needs Practice" card (built in Phase 4) gained a "Generate Practice" button per weak topic, navigating to a new practice-taking page. That page reuses the Phase 3 attempt UI's visual language in a genuinely lighter mode per the instruction — no countdown timer, no per-question navigator grid, no mark-for-review, just a single scrollable list of questions with inline answers and a "Finish Practice" button, since practice is untimed and low-stakes. Finishing shows a dedicated before/after results screen: mastery before → after with a delta badge, the causation disclaimer verbatim from the API, and a per-question correct/incorrect breakdown.

**Decisions:**
- Practice questions/options/responses are a dedicated parallel schema, not a reuse of Phase 3's `Question`/`QuestionOption`/`Response`/`AssessmentAttempt` tables — reusing those would have required either bypassing their timer-expiry/attempt-uniqueness rules (built for real exams, wrong fit for untimed practice) or feeding practice data into the same rows Phase 4's mastery formula reads (the exact real-mastery-inflation risk the "before/after" design above exists to avoid). The dedicated schema is more code but keeps practice's blast radius fully separate from the already-tested exam/analytics engines.
- `selected_option_id` on `PracticeResponse` is a plain nullable FK, not a join table like Phase 3's `ResponseSelectedOption` — safe specifically because practice excludes MULTI_SELECT.
- Full end-to-end demo flow (PDF→extract→publish→attempt→weak-topic→practice→analytics) was run **live against the real dev server** wherever it doesn't require a real Anthropic API key, and the practice-generation AI call step was substituted with a direct DB insert mirroring exactly what `generate_practice_set` would have produced (same tables, same shapes) — this is the same category of limitation as Phase 5's AI generation/extraction/insight (no API key in this environment), not a new one. The resulting live completion showed a real, correctly-computed 56.26% → 54.07% mastery shift after 3 of 4 correct answers, deleted afterward to keep `dev.db` matching the seed script's clean baseline.

**Deferred:** `type`/`recommendation_text` on `Recommendation` support only the one practice-set use case so far — no other recommendation types exist yet (this phase didn't ask for any); a dedicated "My Recommendations" list UI (the Needs Practice card already surfaces the same information more directly, so a separate view would be redundant right now).

**Verified:**
- `pytest` — 126/126 passing.
- `npm run build` — succeeds; the new practice page and dashboard changes compile and type-check cleanly on the first pass.
- Live-verified the full non-AI-dependent practice pipeline against the real running backend and a real seeded student (`rahul.sharma@tutoros.dev`, whose Geometry topic was already "Needs Improvement"/declining from the Phase 4 seed data): confirmed `POST .../practice` gracefully 502s without an API key (same pattern as Phase 5), then seeded a practice set directly, answered 3/4 questions correctly through the real HTTP endpoints, and confirmed `/complete` returned a genuinely computed `mastery_before: 56.26, mastery_after: 54.07, delta: -2.19` with the causation disclaimer attached — and that reopening the same completed set via `GET` correctly reveals correct answers now that it's `COMPLETED`.
- Could not verify actual AI-generated practice content against the real Anthropic API — no key configured in this environment, consistent with every AI-dependent verification since Phase 5. The mocked test suite covers the difficulty-mix enforcement and validation gate exhaustively instead.

## 2026-09-12 — Phase 5: AI features

**Built:**
- AI provider abstraction (`app/ai/`): `AIProvider` ABC with `generate_structured()` (forces strict JSON via Anthropic's tool-use mechanism — a synthetic tool whose `input_schema` is the caller's Pydantic-derived JSON schema, with `tool_choice` pinned to it, not "asking nicely in the prompt") and `generate_text()`. One concrete implementation, `AnthropicProvider`. `get_ai_provider()` is the swap seam — a FastAPI dependency for request-path callers, looked up via the module (`app.ai.get_ai_provider()`) for the PDF pipeline's background task, same pattern Phase 4 established for background-task DB sessions. No key in source control; `ANTHROPIC_API_KEY`/`AI_MODEL` are env-only and a missing key raises a clear error only when a feature is actually invoked, not at boot — **verified live**, since this environment genuinely has no API key configured: `POST /ai/generate-questions` returns a clean 502 with `"ANTHROPIC_API_KEY is not configured..."` rather than crashing.
- Two-layer validation gate (`app/services/ai_validation.py`), used identically by question generation, PDF extraction, and single-question regeneration: Pydantic structural validation (`AIGeneratedQuestionSet`) catches missing fields/wrong types/invalid enums/malformed options; a semantic layer catches duplicate questions and per-type option-shape rules by calling `app/services/question_validation.py::validate_option_shape` — **extracted from Phase 3's publish validator** so "what counts as a valid MCQ" is defined in exactly one place, not reimplemented for AI output. Both layers collect every problem before raising, so a teacher sees the whole list at once.
- AI Question Generator: `POST /ai/generate-questions` (grade/subject/topic/count/difficulty/question_types/total_marks/duration) → validated → `Assessment(status=DRAFT)` + `Question(source="AI_GENERATED")` rows. Synchronous (one bounded LLM turn isn't worth a background job).
- PDF-to-Assessment pipeline: `POST /ai/pdf-extract` validates (PDF-only, 20MB cap), stores via the Phase 2 storage abstraction, creates an `AIExtractionJob` row, and returns 202 **immediately** with a job id — the actual extraction (`pypdf` text extraction → AI segmentation using the same validation gate → topic-name-to-existing-Topic resolution → DRAFT assessment) runs via a `BackgroundTask`, polled via `GET /ai/jobs/{id}`. `AIExtractionJob` isn't in the spec's literal table list — added because "returns immediately with a job id, teacher polls" is meaningless without somewhere to persist status between the POST and the polls, same category as Phase 2/4's schema extensions.
  - **OCR fallback is real code, not a stub**: if `pypdf` extracts under 20 characters (signature of a scanned PDF), the pipeline attempts `pytesseract`+`pdf2image`; those packages (and the Tesseract/Poppler system binaries they need) aren't installed here, so it degrades to a clear, honest job failure rather than crashing — genuinely would work if those deps were installed, with no other code changes.
  - **Not Celery/RQ** — same reasoning as Phase 4's analytics recalculation: no working Docker/Redis in this environment to actually test a real broker against. `BackgroundTasks` gives the identical user-visible contract the spec cares about (request returns immediately, teacher polls a job id); `process_extraction_job()` is the one seam to swap later.
  - **Found and fixed the same class of bug Phase 4 hit**: the background job's DB session must be looked up via the module (`db_session_module.SessionLocal()`), not `from ... import SessionLocal` at call time — the latter binds to the production engine before `tests/conftest.py`'s override can take effect. `test_pdf_extraction_end_to_end` (using a **real PDF** generated with `fpdf2`, real `pypdf` text extraction, only the AI call mocked) verifies the whole pipeline end-to-end.
- AI Extraction Review UI actions: `PATCH /assessments/{id}/questions/{qid}` (new this phase — edit text/topic/difficulty/marks, one general endpoint rather than three separate ones) and `POST /ai/assessments/{id}/questions/{qid}/regenerate` (AI produces one replacement question in the same type/topic/difficulty/marks context). Both blocked (409) once PUBLISHED/CLOSED, same rule as manually-added questions — **AI classifications are never immutable** (spec §15): there is no code path treating an AI-sourced question differently from a manual one once it exists.
- AI Performance Insights: `GET /ai/students/{id}/topics/{topic_id}/insight` builds a small structured profile (`{student, topic, mastery, recent_accuracy, historical_accuracy, trend, questions_attempted}`) from `analytics_service.compute_topic_performance()` (Phase 4, unchanged) — **only this dict**, never raw DB rows, reaches the AI. The response is checked by `validate_no_invented_numbers()`: every numeric token in the AI's text must be within ±1 of a number in the profile (or its rounded form — models paraphrase "55.88" as "56" routinely, and that's not a fabrication) or one of the always-allowed structural numbers (0, 100). Fails once → regenerate with a stricter prompt (one retry); fails twice → **502, the insight is withheld entirely** rather than shown with a possibly-fabricated statistic. Never mentions attendance (not in the profile), so it can't imply the causation `docs/analytics.md` prohibits.
- Frontend: assessments list page gained "Generate with AI" and "Upload PDF" forms (batch/subject/topic pickers, question-type checkboxes for generation; file input + live job-polling for PDF extraction, redirecting to the builder once `COMPLETED`). The builder page (`[id]/page.tsx`) now shows each question's source as a badge ("AI generated"/"AI extracted", nothing shown for manual questions), topic/difficulty inline, and — for AI-sourced questions — Edit (inline text/topic/difficulty/marks form) / Regenerate / Delete actions. Publish is unchanged from Phase 3: same validator, same distinct action, gates AI-sourced assessments exactly as hard as manual ones.
- `docs/ai-pipeline.md`: full pipeline diagrams for all three features, every validation rule, and the two documented limitations (OCR needs system binaries not present here; BackgroundTasks stands in for Celery).
- Tests: 38 new (115 total, all passing, **zero real API calls** — every test uses a `FakeAIProvider` test double via `tests/conftest.py`'s `fake_ai_provider` fixture, which patches both the FastAPI dependency and the module-level lookup the background task uses). Malformed AI JSON rejected at every one of missing-field/duplicate/invalid-marks/invalid-type/malformed-option/missing-correct-answer; PDF pipeline handles a real sample PDF end-to-end with only the AI step mocked; nothing is ever auto-published (explicit assertions after generation and after extraction); provider failures surface as clean 502s, not crashes; insight numeric-safety validated both for grounded and fabricated text.

**Decisions:**
- `validate_option_shape` extracted from Phase 3's `assessment_service.py` into `question_validation.py` rather than duplicated — refactored with the full Phase 3 test suite green before building anything new on top of it.
- Single general `PATCH /assessments/{id}/questions/{qid}` for Edit/Change-topic/Change-difficulty/Change-marks rather than four separate endpoints — they're all "update some subset of this question's fields," and `exclude_unset=True` already gives partial-update semantics for free.
- Numeric-safety validation for insights is a heuristic (regex-extract numbers, tolerance-compare against the profile), not a proof of groundedness — documented explicitly in `docs/ai-pipeline.md` as catching the fabricated-statistic failure mode the spec calls out, not every conceivable way an LLM could mislead.
- PDF topic resolution is case-insensitive exact-name match against the subject's existing topics only — no fuzzy matching, no auto-creating new topics from AI guesses (a wrong auto-created topic would pollute the subject's topic list for every future assessment); an unmatched `topic_name` just leaves `topic_id` null for the teacher to set during review.

**Deferred:** real Celery/RQ wiring and real OCR (both need infrastructure this environment doesn't have — see above); a dedicated insight-display UI (the endpoint is built, tested, and documented, but no frontend button surfaces it yet — the phase's explicit frontend scope was the Extraction Review UI only); topic auto-creation from PDF extraction (a teacher must have already created a topic by that name for it to be linked); a "learning objective" field (mentioned in spec §15's full field list but not part of any table built in Phases 1-5 — would need its own migration).

**Verified:**
- `pytest` — 115/115 passing.
- `npm run build` — succeeds; all pages including the new AI forms compile and type-check cleanly on the first pass.
- Live-checked the provider abstraction's failure path against the real (key-less) backend: registered a teacher, created a batch/subject, called `POST /ai/generate-questions`, got a clean `502 {"error":{"message":"ANTHROPIC_API_KEY is not configured..."}}`  — confirms the whole request path (auth → ownership checks → provider call → error handling) works correctly even though no real generation could be exercised without a key.
- Could not verify an actual AI generation, extraction, or insight against the real Anthropic API — no key is configured in this environment (same limitation as every other external-service phase). All AI-response-shaped logic (validation, persistence, scoring-equivalent correctness) is exhaustively covered by the mocked test suite instead; only the "does Claude actually return the JSON shape we ask for" question is unverified, which is exactly the boundary `AIProvider`/`get_ai_provider()` exists to isolate.

## 2026-09-08 — Phase 4: Analytics

**Built:**
- DB: `performance_snapshots`, `attendance` (migration `79a12d96eb03`). `performance_snapshots` has a `UniqueConstraint(student_id, topic_id)` (one row per student per topic, upserted); `attendance` has `UniqueConstraint(batch_id, student_id, date)` (marking twice on the same day overwrites, doesn't duplicate).
- Analytics service (`app/services/analytics_service.py`, separate from route handlers per §26): `compute_topic_performance()` is the single source of truth for every number described below — the API always calls it live on every read; `performance_snapshots` is a write-only cache populated by the recalculation job, never itself read back, so it can never cause staleness bugs.
  - **Topic accuracy** = `sum(response.score) / sum(question.marks)` over every graded response (score not null) in a finalized attempt tagged to that topic.
  - **Recent vs. historical**: an attempt-count window (`settings.analytics_recent_window`, default 3), not calendar time — deterministic regardless of how spread-out the demo data's timestamps happen to be. Recent = last N attempts' topic ratio (chronological); historical = every attempt *before* that window, falling back to equal recent if the student has ≤N attempts total (no "before" data yet).
  - **Consistency score** = `max(0, 1 - 2×population-stdev(per-attempt ratios)) × 100` — bounded ratios mean stdev is bounded to `[0, 0.5]`, so the `×2` maps the theoretical worst case exactly to 0 and perfect consistency to 100.
  - **Difficulty-adjusted accuracy**: EASY/unrecognized=1.0, MEDIUM=1.5, HARD=2.0 weight per question, applied to both numerator and denominator (a weighted re-average across questions by difficulty, not a bonus).
  - **Trend** reuses the recent/historical split rather than a separate calculation: `insufficient-data` if <2 attempts or no historical baseline yet; otherwise `improving`/`declining`/`stable` based on whether `recent - historical` clears `settings.analytics_trend_threshold` (default 5 percentage points).
  - **Mastery** = `100 × (0.4×recent + 0.3×historical + 0.2×difficulty_adjusted + 0.1×(consistency/100))`, clamped to [0,100]. All four weights are `Settings` fields (`app/core/config.py`), not literals in the formula, per this phase's explicit instruction. Category bands match spec §17 exactly.
  - Full methodology, every constant's rationale, and a worked example (matching `test_mastery_formula_worked_example` exactly) are in **`docs/analytics.md`**, including the required disclaimer that this is a product-defined heuristic, not a validated measurement, and that attendance/performance are never presented as causally linked.
  - **Recalculation**: `BackgroundTasks` (not Celery/RQ) triggered after `POST /attempts/{id}/submit` and after the teacher-grading endpoint, so the triggering request never blocks on it. Docker/Redis still aren't available in this environment (see Phase 0's note), so an actual broker can't even be tested end-to-end right now; `BackgroundTasks` gives the same "don't block the request" guarantee without infrastructure this phase can't verify, and the call site (`recalculate_after_attempt`) is the one seam to swap for a real Celery task later. **Found and fixed a real bug while testing this**: the background task's own DB session must not be looked up via `from app.db.session import SessionLocal` at import time — that binds to the production engine before tests can override it. Fixed by looking it up via the module (`db_session_module.SessionLocal()`) so `tests/conftest.py` can monkeypatch it to the test engine; `test_submit_attempt_triggers_background_recalculation` verifies a real snapshot row lands after a real HTTP submit.
  - **Attendance**: `present_days` counts PRESENT and LATE (a late arrival still attended); percentage is `null` (not 0) when nothing's been marked yet, to distinguish "no data" from "zero attendance."
- Routes: `GET /students/{id}/performance`, `GET /students/{id}/topics/{topic_id}/performance`, `GET /batches/{id}/attention-panel`, `GET /batches/{id}/class-performance` (average/median/high/low/distribution + per-topic average/median/high/low, matches spec §21's batch→subject→topic drill-down request compactly in one endpoint rather than a separate route per level), `GET /assessments/{id}/analytics` (question-level percent-correct/avg-time per §21), `POST/GET /batches/{id}/attendance`, `GET /students/{id}/attendance`.
- Tests: 19 new tests (77 total, all passing). Topic accuracy hand-computed against exact expected fractions; **the full mastery-formula worked example matches the numbers documented in `docs/analytics.md` to the hundredth**; mastery category band boundaries; difficulty-adjustment demonstrably rewards a HARD question over an EASY one; trend detection parametrized across 5 synthetic sequences covering all four trend outcomes; ungraded responses correctly excluded from every calculation; snapshot upsert doesn't duplicate; attendance marking/overwrite/percentage/authorization (student can't see another student's attendance, teacher can't mark another teacher's batch).
- Seed script extended significantly: 3 topics (Algebra/Geometry/Trigonometry) now actually tagged onto questions (the Phase 3 seed assessment had none — analytics would have had zero data to show without this fix); 4 rounds of practice quizzes across all 3 topics for 3 students with deliberately different trajectories (Rahul: mastered-and-stable Algebra, declining Geometry, improving Trigonometry; Ishita: improving-but-still-weak Algebra; Arjun: perfect/stable across the board) so the Attention Panel and class charts show real variety, not a flat line; 10 days of varied attendance (~50%–100% across students) for the class-performance chart.
- Frontend: dashboard root (`/dashboard`) now branches by role instead of redirecting students away — teachers keep the batches/students Overview, students get a real "Your Progress" view (overall mastery, strengths, needs-practice list with trend arrows) driven entirely by `/students/{id}/performance`, matching spec §10's example format. New teacher-only Analytics page: a batch selector, two Recharts bar charts (class average score/attendance/mastery; per-topic class-average mastery), and the Attention Panel table (student | topic | mastery | trend arrow) exactly as specified in §9. A shared `TrendArrow` component maps trend → ↑/↓/→/– badge, reused on both the student dashboard and the Attention Panel.

**Decisions:**
- Class-performance's per-topic breakdown (average/median/high/low/student_count) is folded into the single `class-performance` endpoint rather than a separate batch→subject→topic drill-down route — it's the same aggregation the frontend chart needs, and a separate route would just be more surface area for identical data.
- `overall_mastery` (student dashboard) is an unweighted mean across the student's topics with data — simple and explainable, documented in `docs/analytics.md` as a deliberate simplification (a student strong in 3 topics and critical in 1 isn't swamped by whichever topic happens to have the most questions).
- Attempt-level granularity (not per-question) for recent/historical/consistency/trend — matches the spec's own worked example (one percentage per *test*) and its explicit "variation... across attempts" wording for consistency, even though `accuracy`/`difficulty_adjusted_accuracy` use the finer question-level granularity. Both are documented explicitly in `docs/analytics.md` since mixing granularities without explanation would be confusing.
- Still on local SQLite pending Docker; no new friction from that this phase.

**Deferred:** actual Celery/RQ wiring (BackgroundTasks stands in, see above); an attendance-*marking* UI (backend fully built and tested, but the frontend bullet for this phase only asked for the Attention Panel + charts + student dashboard, not a marking form — attendance data exists this phase only via the seed script); `GET /students/{id}/topics/{topic_id}/performance` has no dedicated frontend consumer yet (single-topic drill-down); attendance-vs-performance correlation display (backend has both numbers available, but no UI presents them side-by-side yet — when it does, `docs/analytics.md`'s no-causation language must be followed).

**Verified:**
- `pytest` — 77/77 passing.
- `npm run build` — succeeds; `/dashboard` (both role branches) and `/dashboard/analytics` compile and type-check cleanly.
- Ran the real seeded data through every new endpoint live: attention-panel correctly surfaced each student's actual weakest topic with the correct trend arrow (Ishita→Algebra/improving, Rahul→Geometry/declining, Arjun→Algebra/stable-100), class-performance produced a real score distribution and non-trivial per-topic averages, and a specific student's `/performance` response matched the seed script's intended trajectory exactly (Rahul: Algebra mastered/stable, Geometry declining/needs-improvement, Trigonometry improving/developing).
- Could not drive an actual browser in this environment — the Recharts bar charts and the student dashboard's card layout are implemented and API-verified but not visually confirmed. Please look at `/dashboard/analytics` as `priya.nair@tutoros.dev` and `/dashboard` as `rahul.sharma@tutoros.dev` / `password123` (seeded directly by the script, so — unlike students added through the teacher's "add student" UI — this login works) to confirm the charts and student progress view render as expected.

## 2026-09-08 — Phase 3: Assessment engine

**Built:**
- DB: `assessments`, `questions`, `question_options`, `assessment_attempts`, `responses` (migration `68ec7a248ed1`), plus one addition beyond the literal spec table: `response_selected_options`, a join table. A single nullable `selected_option` FK column (as sketched in spec §7) cannot represent MULTI_SELECT's "more than one chosen option" — this join table replaces it and is used for MCQ/MULTI_SELECT/TRUE_FALSE alike (1 row for single-select types, N rows for multi-select). `assessment_attempts` has a `UniqueConstraint(assessment_id, student_id)` — one attempt per student per assessment, no retakes in this MVP. `responses` has `UniqueConstraint(attempt_id, question_id)` — autosave upserts the same row rather than accumulating history.
- Backend service (`assessment_service.py`, the most safety-critical file in the codebase so far):
  - **Publish validation** (`validate_for_publish`): no questions at all → reject; MCQ needs ≥2 options and exactly 1 correct; MULTI_SELECT needs ≥2 options and ≥1 correct; TRUE_FALSE needs exactly 2 options and exactly 1 correct; NUMERICAL needs exactly 1 stored answer that parses as a float; SHORT_ANSWER/LONG_ANSWER must have zero options (the "no orphaned options" rule); and the sum of all question marks must equal the assessment's declared `total_marks`. All violations are collected and returned together (not fail-fast) so a teacher fixes everything in one pass.
  - **Grading** (`_grade_objective`): MCQ/TRUE_FALSE/MULTI_SELECT compare the submitted option-id set against the correct option-id set exactly (all-or-nothing — a MULTI_SELECT answer missing one of two correct options scores 0, not partial credit). NUMERICAL parses the student's text and the stored answer as floats and compares with a `1e-6` epsilon (avoids float-representation false negatives); unparseable input is simply wrong, not an error, so a mid-typing autosave never fails. Score/is_correct are computed **only from data already in the database** — nothing from the request body ever reaches the score field for objective types. SHORT_ANSWER/LONG_ANSWER always get `score=None` until a teacher grades them via the dedicated grade endpoint, which itself refuses to touch objective questions (409) and refuses a score exceeding the question's marks (422).
  - **Timer enforcement** is lazy, not a background job: `_check_and_expire` runs at the top of every attempt-touching call (get attempt, submit response, finalize) and flips `IN_PROGRESS → EXPIRED` the moment `now > started_at + duration_minutes` is observed, finalizing with whatever responses exist so far. A response submitted after expiry gets 403 and the same expiry check fires as a side effect, so the attempt never dangles. Submitting an already-expired/-submitted attempt again is a safe no-op (still 200, returns the existing finalized state).
  - **Authorization**: a student can only start an attempt for a PUBLISHED assessment in a batch they're actively enrolled in (DRAFT/REVIEW/CLOSED-to-non-attempted-students all 404, not 403, to avoid confirming existence); can only read/write their own attempt (another student's attempt is 404, never leaked); can never see `is_correct` on any question while their attempt is `IN_PROGRESS` (only revealed via `/attempts/{id}/review` once finalized). A teacher can only manage/publish/grade their own assessments.
  - Correct-answer visibility is enforced at serialization, not by trusting the caller: `_question_read(..., include_correct: bool)` strips `is_correct` to `None` for students, and the review endpoint (`GET /attempts/{id}/review`) itself refuses (409) to reveal anything while `status == IN_PROGRESS`.
- Routes: `POST/GET /assessments`, `GET/PATCH /assessments/{id}`, `POST/GET /assessments/{id}/questions`, `DELETE .../questions/{id}`, `POST .../publish`, `POST .../close`, `POST .../attempts` (start/resume), `GET /attempts/{id}`, `GET/POST /attempts/{id}/responses`, `POST /attempts/{id}/submit`, `GET /attempts/{id}/review`, `GET /assessments/{id}/attempts` (teacher roster), `PATCH .../attempts/{id}/responses/{question_id}/grade`.
- Tests: 24 new tests (58 total, all passing). Publish validation exhaustively covers every rule above with its own test (empty correct-set, marks mismatch, orphaned options on subjective, invalid numerical answer, success case). Attempt tests cover the full autosave→submit flow, **backend-authoritative scoring verified for all four objective types** (including the MULTI_SELECT partial-match-scores-zero case and the NUMERICAL unparseable-text-scores-zero case), resubmission overwriting rather than duplicating, teacher grading updating `total_score`, **timer expiry actually flipping status and blocking further responses**, **submit-after-expiry being a safe no-op**, and the two authorization-critical cases the spec called out by name: a student can't touch another student's attempt, and can't attempt an unpublished assessment.
- Seed script extended: one PUBLISHED assessment ("Algebra & Geometry Quiz", 5 questions — one of every type, 10 marks total) plus one fully completed attempt scoring 8/10 objectively with its short-answer response left ungraded, so the teacher's grading UI has something real to grade on a fresh clone.
- Frontend: assessment list (teacher: create + status badges; student: start/view-results), a builder page (`[id]/page.tsx` + `question-form.tsx`) with a type-aware question form (radio/checkbox correctness pickers per type, a single numeric field for NUMERICAL, no options UI for subjective types) and a Publish button that surfaces every validation error returned by the backend at once, a test-taking page (`[id]/attempt/page.tsx`) with an instructions screen, live countdown timer that **auto-submits at zero**, a question-navigator grid (answered/marked-for-review/current color-coded), per-question autosave (immediate for radio/checkbox, 600ms debounced for text/number) with a saving/saved/error indicator, mark-for-review, prev/next navigation, and a results view driven by `/attempts/{id}/review`. A teacher attempts/grading page (`[id]/attempts/page.tsx`) lists every student's status/score with an expandable per-attempt panel to enter scores for ungraded subjective responses.

**Decisions:**
- `response_selected_options` join table instead of the spec's literal singular `selected_option` column — see above; this isn't scope creep, MULTI_SELECT is explicitly required and cannot work otherwise.
- MULTI_SELECT grading is all-or-nothing, not partial credit — the spec doesn't specify partial-credit rules, and all-or-nothing is the simplest defensible default. Revisit if a real course needs partial credit; it would be a change to one function (`_grade_objective`).
- `total_marks` is a teacher-declared field checked against the actual sum at publish time (not auto-computed from questions) — this is what makes the spec's "marks must sum correctly" validation a real, testable check rather than a tautology.
- Timer expiry is checked lazily on access, not via a Celery background job — Celery/Redis background processing is explicitly out of scope until a later phase; lazy-checking on every attempt-touching endpoint gives the same user-visible guarantee (you cannot get graded time beyond your allotment) without infrastructure this phase doesn't need yet.
- No question-editing endpoint (`PATCH` on a single question) — only add/delete while DRAFT/REVIEW. Deferred; a teacher can delete-and-recreate a question in the builder.
- Still on local SQLite pending Docker.

**Deferred:** question `topic_id`/`difficulty` are accepted by the schema but unused by any UI control yet (no topic/difficulty picker in the question form) — wire up once Phase 4 analytics needs them. `REVIEW` status exists in the enum and is a legal pre-publish state but nothing in the UI currently transitions an assessment into it (only DRAFT→PUBLISHED is exposed) — add a "Send for review" action if a real second-teacher-approval workflow is needed. No question reordering UI (order_index is set by insertion order only).

**Verified:**
- `pytest` — 58/58 passing, including exhaustive scoring correctness for MCQ/MULTI_SELECT/TRUE_FALSE/NUMERICAL and the timer-expiry/authorization suite.
- `npm run build` — succeeds; all three new assessment routes (list, builder, attempt, attempts) compile and type-check cleanly on the first pass.
- Exercised the complete real flow against the live dev backend end-to-end, matching the frontend's exact request shapes: seeded a fresh student, enrolled them, started an attempt (confirmed correct answers are hidden), submitted one wrong + three correct + one subjective response, finalized, and confirmed `total_score` landed at exactly 6 (0+3+1+2, matching hand-computed expectations) before the teacher's grading endpoint pushed the seeded demo attempt from 8→10 after grading its short answer. Reseeded fresh afterward.
- Could not drive an actual browser in this environment (still no headless browser available) — the countdown-timer auto-submit behavior, question-navigator color states, and the builder's inline validation-error list are implemented and API-verified but not visually confirmed; please click through creating a question of each type, publishing, and taking the seeded "Algebra & Geometry Quiz" as a fresh student account once.

## 2026-09-08 — Phase 2: Homework

**Built:**
- DB: `homework`, `homework_attachments`, `homework_submissions` (migration `50b9bb1bd83c`). `homework_submissions` has a `UniqueConstraint(homework_id, student_id)` — a student has exactly one submission row per homework, resubmission updates it in place (matches "replace before deadline" from the spec, and keeps roster math simple: one row per student, not a growing history).
- Storage abstraction (`app/storage/`): `StorageBackend` ABC (`save`/`read`/`delete`) with one `LocalDiskStorage` implementation for dev. `get_storage()` factory branches on `settings.storage_backend` (only `"local"` implemented; a `# ponytail:` comment marks exactly where an `S3Storage` class plugs in later — nothing else in the codebase touches paths directly, homework/service code only ever calls `get_storage()`).
- Upload validation (`app/services/upload_service.py`): MIME-allowlist (pdf/png/jpg/jpeg/doc/docx) — reject anything else with 415; size cap (10MB, configurable) — reject over with 413; storage filename is `uuid4().hex + extension`, where the extension comes from the allowlist table keyed by MIME type, **never** from the client-supplied filename. The original filename is kept only as display metadata in the DB.
- Backend service (`homework_service.py`): create homework (validates the batch is owned by the calling teacher, subject/topic exist), list/detail scoped by role (teacher sees own; student sees only batches they're actively enrolled in), `PATCH` for teacher-only edits including `allow_late_submissions` (this is the "reopen" mechanism — a boolean flag rather than a reopen-history table, since nothing in scope needs to know reopen history yet), submission upsert with deadline enforcement (`403` after `due_date` unless `allow_late_submissions`), and roster aggregation (submitted/late/pending computed by left-joining active `batch_students` against submissions — a student with no row is "pending", not a separate DB state).
- Routes: `POST/GET /homework`, `GET/PATCH /homework/{id}`, `GET /homework/{id}/attachments/{attachment_id}/file`, `POST /homework/{id}/submissions`, `GET /homework/{id}/submissions` (teacher roster), `GET /homework/{id}/submissions/me`, `GET/GET-file /homework/{id}/submissions/{student_id}`.
- Tests: 12 new tests (34 total, all passing) — creation with attachment, unsupported file type rejected (415), teacher can't create homework on another teacher's batch (404), attachment download scoped to owner/enrolled-student, student sees only their own batches' homework, **submit before deadline succeeds, submit after deadline rejected (403), submit after deadline succeeds once reopened (LATE status)**, resubmission replaces the row instead of duplicating, **student not in the batch can't submit (404)**, **student can't view another student's submission (404) while the teacher can (200)**, roster correctly distinguishes submitted/pending.
- Seed script extended: 2 homework assignments on Class 10-A Mathematics — one upcoming (2 submitted, 3 pending), one past-due with `allow_late_submissions=true` (1 on-time submission, 1 late submission, 3 still pending) — verified live via the API, not just in tests.
- Frontend: role-aware dashboard nav (this phase surfaced that Phase 1's nav/Overview assumed every dashboard visitor was a teacher — students would have hit 403 on Batches/Students/Subjects/Overview; fixed by branching nav items on role and redirecting students from `/dashboard` to `/dashboard/homework`). Teacher homework list (create form using React Hook Form + Zod per this phase's explicit ask, submitted/late/pending badges per assignment) → detail page (roster table, attachment/submission downloads, "Reopen for late submissions" action). Student homework list (due-date countdown, inline upload/replace control, submitted/late/pending badge, attachment downloads). Downloads go through an authenticated `fetch` + blob + synthetic `<a>` click, since the API requires a Bearer token that a plain `<a href>` can't carry.

**Decisions:**
- `homework_submissions` gained `file_name`/`storage_key`/`mime_type`/`file_size`/`score`/`feedback` columns beyond the spec's literal table listing — a submission needs an actual uploaded file, and `score`/`feedback` are in the spec's schema description even though grading itself is a later phase; added now to avoid a near-future migration, left unused until grading exists.
- `subject_id` is required on homework, `topic_id` optional — the spec doesn't state nullability explicitly; this matches how the seed data and UI actually use it (topic-level tagging is a nice-to-have, subject is not).
- Submissions are single-file, not multi-attachment like homework creation — the spec only asks for "multiple file attachments" on homework creation, not submissions. Extend if a real use case needs it.
- Newly-created students still get an unusable random password (carried over from Phase 1) — still deferred, still tracked with the same `# ponytail:` comment.
- Still on local SQLite (`sqlite:///./dev.db`) — Docker Desktop's engine still isn't starting on this machine. No new friction from that this phase.

**Deferred:** grading UI/endpoints (score/feedback columns exist but nothing writes them), real S3/R2/MinIO storage backend, homework editing beyond `allow_late_submissions`/basic fields, submission history (only the latest submission is kept).

**Verified:**
- `pytest` — 34/34 passing.
- `npm run build` — succeeds; `/dashboard/homework` and `/dashboard/homework/[id]` compile and type-check (had to fix three TS errors from the shadcn `Select` component actually wrapping Base UI, not Radix, in this project's shadcn version — its `onValueChange` hands back `string | null`, not `string`).
- Exercised the exact multipart request shape the frontend sends against the live dev backend with curl (create homework with a real file attachment, list it back, download the attachment, and byte-for-byte confirm the downloaded content matches what was uploaded). Reseeded fresh afterward so the dev DB reflects only the seed script's data, not curl test artifacts.
- Could not drive an actual browser in this environment (still no headless browser available) — please click through the teacher and student homework views once against the reseeded data (teacher: `priya.nair@tutoros.dev` / `password123`; student: `ishita.singh@tutoros.dev`-style seeded accounts don't have known passwords since they were teacher-created — register a fresh student account and have the teacher add it to a batch to test the student view end-to-end in the browser).

## 2026-09-08 — Phase 1: Core academic management

**Built:**
- DB: `teacher_profiles`, `student_profiles`, `batches`, `batch_students`, `subjects`, `topics` (migration `f19e11a0e3a0`, chained after Phase 0's). `batch_students` uses a composite PK `(batch_id, student_id)`, which doubles as the required index; `batches.teacher_id` and `topics.subject_id` are indexed FKs.
- Backend service layer: `batch_service.py` (create/list/update batches, add student to batch — creates a new STUDENT user or attaches an existing one by email, roster listing), `student_service.py` (teacher's student list, single-student lookup scoped to the teacher's own batches, dashboard counts), `subject_service.py` (subjects/topics are global catalog data per the spec's schema — no per-teacher ownership column exists for them, so no ownership check applies there, only role).
- Authorization: `require_role(*roles)` dependency added to `app/core/deps.py`. All batch/student endpoints resolve "owned by this teacher" via a real join through `batch_students`/`batches`, not a trusted client-supplied id. Unowned/unrelated resources return 404 (not 403) to avoid confirming a resource's existence to someone who shouldn't see it.
- Routes: `POST/GET /batches`, `GET/PATCH /batches/{id}`, `GET/POST /batches/{id}/students`, `GET /students`, `GET /students/{id}` (teacher sees own batches' students; a student can only see themselves), `POST/GET /subjects`, `POST/GET /topics`, `GET /teachers/dashboard`.
- Tests: 15 new tests (22 total, all passing) — batch CRUD, **Teacher A blocked from Teacher B's batch on GET/PATCH/roster (404)**, student blocked from creating batches (403), **student blocked from reading another student's record (404)**, a self-registered student can read their own record, add-existing-vs-new-student paths, duplicate-add rejected (409), subject/topic creation and the student-role-blocked case.
- Seed script (`backend/scripts/seed.py`, run via `python -m scripts.seed`): 2 teachers, 3 batches, 15 realistically-named students spread across batches. All seeded accounts use password `password123`.
- Frontend: dashboard shell (`/dashboard/layout.tsx`) with sidebar nav + logout, shared `useAuth` hook. Pages: Overview (real batch/student counts from `/teachers/dashboard`), Batches (list + create form), Batch detail (roster + add-student form), Students (cross-batch list), Subjects & Topics (two-pane manager). All list views handle loading (skeletons), empty, and error states explicitly.

**Decisions:**
- Adding a brand-new student to a batch generates a random password the student never receives — there's no invite/credential-delivery flow yet. `# ponytail:` comment on `add_student_to_batch` marks this as a known gap with the upgrade path (proper invite or teacher-set temp password) noted, deferred until a phase actually needs students to self-serve onboard.
- Subjects/topics have no owner field, matching the schema literally specified in spec §7 — any teacher can create/see any subject or topic. If per-teacher subject scoping turns out to matter later, that's a schema change, not a bug fix.
- No TanStack Query yet — every list page is a plain `useState`/`useEffect` fetch. Five simple GET-driven pages don't justify a data-fetching library; revisit if request deduplication/caching actually becomes a pain point (e.g. once the same data is needed across more pages, or mutations need cache invalidation).
- Still running the backend against local SQLite (`backend/.env` → `sqlite:///./dev.db`) since Docker Desktop's engine still isn't starting on this machine (see the 2026-09-08 note in Phase 0 above). No new blockers from that this phase — migration syntax remains dialect-generic.

**Deferred:** everything outside Phase 1 scope — homework, assessments, analytics, AI, personalization, rate limiting, and student self-service registration/invites.

**Verified:**
- `pytest` — 22/22 passing.
- `npm run build` — succeeds; `/dashboard`, `/dashboard/batches`, `/dashboard/batches/[id]`, `/dashboard/students`, `/dashboard/subjects` all compile and type-check.
- Ran the seed script against the live dev backend and hit every new endpoint via curl with a real seeded teacher's JWT: `/teachers/dashboard` → correct counts, `/batches` → correct rows with `student_count`. Frontend dev server confirmed serving all four new routes (200s); the actual browser/visual check is still pending on the user's side since no headless browser is available in this environment.

## 2026-09-07 — Phase 0: Foundation

**Built:**
- Monorepo: `/backend` (FastAPI), `/frontend` (Next.js 16 + TS + Tailwind v4 + shadcn/ui), `/docs`.
- Backend: app skeleton (`app/main.py`), Pydantic settings from env (`app/core/config.py`, `.env.example`), centralized JSON error handlers for HTTP/validation/unhandled exceptions (`app/core/errors.py`), logging config, health check at `GET /health`.
- Service-layer structure already in place for auth (`app/services/auth_service.py`) so route handlers stay thin, per spec §26.
- DB: `users` table (UUID pk, name, email unique, password_hash, role enum, timestamps) via SQLAlchemy 2.0 models + one Alembic migration (`eb78b5d0bb29_create_users_table`), using dialect-generic `Uuid`/`Enum` types so the same migration runs on both Postgres and SQLite.
- Auth: bcrypt password hashing (passlib), JWT issuance/verification (python-jose), `get_current_user` dependency (`app/core/deps.py`), `POST /auth/register`, `POST /auth/login`, `GET /auth/me` (protected). 7 pytest tests covering registration, duplicate email, login success/failure, and protected-route access with/without/invalid token — all passing.
- `docker-compose.yml` at repo root: Postgres 16 + Redis 7, both with healthchecks, for local dev.
- Frontend: login/register pages (shadcn Card/Input/Label/Button, client-side form state, no RHF/Zod yet since there's only 2-3 fields per form), typed fetch wrapper (`src/lib/api.ts`) with a shared `ApiError`, `localStorage`-based token helper (`src/lib/auth.ts`), placeholder `/dashboard` page that client-side redirects to `/login` when no token exists and fetches `/auth/me` to render the user.

**Decisions:**
- Route protection is client-side (`localStorage` token + `useEffect` guard), not Next.js middleware/cookies — there's nothing sensitive to protect server-side yet (SSR pages don't fetch anything), and JWT-in-cookie plus middleware is unnecessary complexity for a placeholder page. Revisit if/when pages need server-rendered authenticated data.
- Test suite runs against in-memory SQLite (`StaticPool`) instead of requiring a live Postgres for `pytest`, since Docker isn't available in this environment either. Migrations and models use SQLAlchemy's dialect-generic `Uuid`/`Enum` types specifically so this works identically against Postgres in real dev/deploy. `docker-compose.yml` still provisions real Postgres+Redis for actual local development.
- No React Hook Form + Zod yet — deferred until Phase 2 (homework forms) where form complexity actually justifies it; today's 2 forms (login/register) are simple enough for plain `useState`.

**Deferred (explicitly out of scope for Phase 0):**
- Everything beyond auth: batches, students, subjects, topics, homework, assessments, analytics, AI, Celery/RQ workers (Redis is provisioned but unused so far), rate limiting, structured request logging beyond basic config.

**Verified:**
- `pytest` — 7/7 passing (SQLite in-memory).
- `npm run build` — succeeds, all 4 routes (`/`, `/login`, `/register`, `/dashboard`) compile and prerender.
- Manually ran both dev servers together (backend on SQLite file DB, frontend against it) and exercised the full auth flow via curl: register → 201 + token, duplicate register → 409, login with wrong password → 401, `/auth/me` with valid token → 200, without token → 401.
- Could **not** verify `docker compose up` — Docker is not installed in this environment. `docker-compose.yml` is written against standard Postgres 16 / Redis 7 images with no unusual config; run `docker compose up -d` and then the migration command below on your machine to confirm.

**Update 2026-09-08:** User's machine has WSL2 installed but Docker Desktop's engine won't start yet (stuck WSL distro registration) — Postgres/Redis are not running locally. To unblock manual testing in the meantime, `backend/.env` was pointed at `sqlite:///./dev.db` instead of Postgres, and `backend/.env` port was set to 8050 (8000 was in use), with `frontend/.env.local` updated to match (`NEXT_PUBLIC_API_URL=http://localhost:8050`) and `CORS_ORIGINS=["http://localhost:3000"]`. Confirmed full register→CORS→JWT→/auth/me flow works through the real browser. **This is a temporary local workaround, not a design change** — switch `backend/.env`'s `DATABASE_URL` back to the Postgres one once `docker compose up -d` works, since SQLite doesn't enforce the same constraints/types as Postgres in edge cases.
