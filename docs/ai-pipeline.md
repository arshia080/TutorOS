# AI pipeline

Three independent AI-backed features share one provider abstraction and one
validation gate. None of them can ever publish an assessment — every one lands
in `DRAFT` for a teacher to review, edit, and explicitly publish (which reuses
the exact Phase 3 publish validator, unchanged).

## Provider abstraction

```
app/ai/base.py              AIProvider (ABC): generate_structured(), generate_text()
app/ai/anthropic_provider.py AnthropicProvider(AIProvider) -- the only concrete implementation
app/ai/__init__.py           get_ai_provider() -- the swap point
```

`AIProvider` is two methods, both prompt-in:

- `generate_structured(prompt, json_schema, tool_name) -> dict` — forces the
  model to return data matching `json_schema` using Claude's tool-use
  mechanism: a synthetic tool is defined with `input_schema = json_schema` and
  `tool_choice` is pinned to it, so the model's only valid move is to call that
  tool with matching arguments. This is what "strict structured JSON output"
  means for Claude specifically — not asking nicely in the prompt.
- `generate_text(prompt) -> str` — a plain completion, used only for the
  performance-insight narrative (§20), which doesn't need a schema.

Swapping providers (e.g. to OpenAI) means writing one new class implementing
these two methods and changing `get_ai_provider()` — nothing in
`ai_question_service.py`, `ai_pdf_service.py`, or `ai_insight_service.py`
touches Anthropic-specific code.

Configuration is environment-only (`ANTHROPIC_API_KEY`, `AI_MODEL` — see
`app/core/config.py`); there is no key in source control, and a missing key
raises a clear `AIProviderError` **only when a feature is actually invoked**,
not at import/boot time — the app runs fine without a key configured until
someone calls an AI endpoint.

## The validation gate (never bypassed)

**Every** piece of AI output — question generation, PDF extraction, and
single-question regeneration — passes through the same two-layer gate before
touching the database, in `app/services/ai_validation.py`:

1. **Structural** (`AIGeneratedQuestionSet.model_validate(raw)`, Pydantic): catches
   missing fields, wrong types, invalid `question_type` values, malformed
   options — a `pydantic.ValidationError` becomes a list of plain-English error
   strings.
2. **Semantic** (`_semantic_errors`): things Pydantic's type system can't
   express —
   - duplicate questions (case-insensitive, whitespace-trimmed exact match),
   - per-question-type option-shape rules, via
     `app/services/question_validation.py::validate_option_shape` — **the
     exact same function the Phase 3 publish validator calls**, so "what
     counts as a valid MCQ" is defined in exactly one place regardless of
     whether the question was typed by a teacher, generated, or extracted.

Both layers collect **every** problem before raising `AIValidationError(errors)`
— a teacher (or a test) sees the whole list at once. Nothing is written to the
database unless validation passes completely; a partially-valid batch of
questions is rejected as a whole.

## 1. AI Question Generator (§14)

```
POST /ai/generate-questions
  {batch_id, subject_id, topic_id?, grade, count, difficulty,
   question_types, total_marks, duration_minutes}
    │
    ▼
build a prompt encoding every input field + the option-shape rules
    │
    ▼
provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), "return_questions")
    │
    ▼
validate_generated_question_set(raw)  ── fails ──► 422 {errors: [...]}, nothing persisted
    │ passes
    ▼
create Assessment(status=DRAFT) + Question(source="AI_GENERATED") + QuestionOption rows
    │
    ▼
201, teacher reviews/edits, then explicitly calls POST /assessments/{id}/publish
```

Synchronous — a generation call is one bounded LLM turn, not worth a
background job.

## 2. PDF-to-Assessment pipeline (§13)

```
POST /ai/pdf-extract (multipart: file, batch_id, subject_id)
    │
    ▼
validate: content-type must be application/pdf, size ≤ 20MB
    │
    ▼
store the PDF bytes via the storage abstraction (app/storage/, Phase 2)
    │
    ▼
create AIExtractionJob(status=PENDING), return 202 {job_id, status} IMMEDIATELY
    │
    ▼  (FastAPI BackgroundTask, see "Why not Celery?" below)
job.status = PROCESSING
    │
    ▼
extract text: pypdf per-page text extraction
    │
    ▼ (if extracted text is near-empty -- likely a scanned/image PDF)
OCR fallback: pytesseract + pdf2image, IF installed -- see below
    │
    ▼
build a prompt with the raw extracted text (including any answer-key section)
+ the subject's existing topic names, asking the model to segment into
questions, extract options, use the answer key to mark correct answers,
and guess topic_name + difficulty per question
    │
    ▼
provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), "return_extracted_questions")
    │
    ▼
validate_generated_question_set(raw)  ── fails ──► job.status = FAILED, error_message set, no assessment created
    │ passes
    ▼
create Assessment(status=DRAFT) + Question(source="AI_EXTRACTED") rows,
resolving each question's topic_name to an existing Topic by case-insensitive
name match (or leaving topic_id null if none matches -- the teacher sets it
in review)
    │
    ▼
job.status = COMPLETED, job.assessment_id = <new assessment>

GET /ai/jobs/{job_id}   ← the teacher polls this
```

`AIExtractionJob` (migration `ac062c8628b6`) isn't in the product spec's
literal table list (§7) — it exists because "the HTTP request must return
immediately with a job ID; the teacher polls" is meaningless without
somewhere to persist job status between the POST and the polling GETs. Same
category of necessary addition as Phase 2's storage abstraction or Phase 4's
`performance_snapshots`.

### Why not Celery/RQ?

The spec asks for a "background job (Celery/RQ)". This environment has no
working Docker/Redis (see `docs/PROGRESS.md`, Phase 0 onward) — there's no way
to actually run or test a real broker here. `BackgroundTasks` (stdlib-adjacent,
built into FastAPI) gives the identical user-visible contract the spec
actually cares about — **the triggering request returns immediately, the
teacher polls a job id** — without infrastructure this phase can't verify end
to end. `process_extraction_job()` is the single seam to swap for a real
Celery task later (`background_tasks.add_task(...)` becomes
`process_extraction_job.delay(...)`); nothing about its internals or the
`AIExtractionJob` table would need to change.

One real bug surfaced and fixed while wiring this (same class of bug Phase 4
hit with analytics recalculation): the background task must look up its DB
session via `app.db.session.SessionLocal` **through the module**, not via
`from app.db.session import SessionLocal` at import time — the latter binds to
whatever engine existed when the module first loaded, invisible to test
overrides. `tests/conftest.py`'s `_isolate_background_task_sessions` fixture
patches the module attribute so the test suite's in-memory engine is what
background tasks actually see.

### OCR fallback — real code, honestly limited

`_extract_text_with_ocr_fallback()` in `app/services/ai_pdf_service.py` is a
genuine, working code path: if `pypdf` extracts fewer than 20 characters of
text (the signature of a scanned/image-only PDF), it attempts
`pytesseract` + `pdf2image`. Those packages — and the Tesseract OCR engine and
Poppler binaries they wrap — are **not installed in this environment**
(they'd be dead weight without the underlying system binaries, which can't be
verified here either). The fallback function catches the resulting
`ImportError` and fails the job with a clear, honest message rather than
crashing or silently returning empty text. Installing
`pip install pytesseract pdf2image` plus the Tesseract/Poppler system
binaries makes this path live with no other code changes.

## 3. AI Extraction Review UI (§13 actions)

Frontend: `frontend/src/app/dashboard/assessments/[id]/page.tsx` (the same
builder page from Phase 3) now recognizes `question.source` and renders an
"AI extracted" / "AI generated" badge, plus per-question actions:

| Action | Backend |
|---|---|
| Edit | `PATCH /assessments/{id}/questions/{qid}` (new this phase) |
| Delete | `DELETE /assessments/{id}/questions/{qid}` (Phase 3, unchanged) |
| Regenerate | `POST /ai/assessments/{id}/questions/{qid}/regenerate` |
| Change topic / difficulty / marks | same `PATCH` endpoint — one general-purpose edit, not three separate ones |

All of these are blocked (409) once the assessment is `PUBLISHED`/`CLOSED`,
same rule as manually-added questions. **AI classifications are never
immutable** (§15) — there is no code path that treats an AI-sourced question
differently from a manually-typed one once it exists in the database; `source`
is display-only metadata.

**Publish** is a separate, deliberate action
(`POST /assessments/{id}/publish`) that reuses the unmodified Phase 3
`validate_for_publish()` — an AI-extracted or -generated assessment is held to
exactly the same bar (no empty correct-answer sets, no orphaned options, marks
must sum correctly) as one a teacher typed by hand. Nothing in this phase
weakens or bypasses that gate.

## 4. AI Performance Insights (§20)

```
GET /ai/students/{id}/topics/{topic_id}/insight
    │
    ▼
analytics_service.compute_topic_performance(db, student_id, topic_id)  -- Phase 4, unchanged
    │  (404 if no data yet)
    ▼
build_topic_profile(): {student, topic, mastery, recent_accuracy,
                         historical_accuracy, trend, questions_attempted}
    │   <- this small dict is the ONLY thing that reaches the AI. No raw
    │      responses/attempts/DB rows are ever included in the prompt.
    ▼
provider.generate_text(prompt asking the model to explain, not invent, these numbers)
    │
    ▼
validate_no_invented_numbers(text, profile)  ── fails once ──► regenerate with a stricter prompt (max 1 retry)
    │                                          ── fails twice ──► 502, insight withheld entirely
    │ passes
    ▼
200 {insight: "..."}
```

`validate_no_invented_numbers()` (`app/services/ai_insight_service.py`)
extracts every numeric token from the model's text (regex `\d+\.?\d*`) and
checks each one is within ±1 of a number actually present in the profile (or
its rounded form — models paraphrase "55.88" as "56" routinely, and that's not
a fabrication). `0` and `100` are always allowed (structural — "capped at
100%" isn't a claim about this student specifically). Anything else — an
invented "improved by 25% over 10 tests" — fails validation. This is a
heuristic, not a proof of groundedness; it catches the fabricated-statistic
failure mode the spec calls out, not every possible way an LLM could mislead.
If it fails twice in a row, **the insight is never shown** — the endpoint
returns 502 rather than ship text that might contain a made-up number.

The endpoint never mentions attendance (the profile doesn't include it), so
there's no risk of it implying an attendance/performance causal link — see
`docs/analytics.md`'s no-causation rule.
