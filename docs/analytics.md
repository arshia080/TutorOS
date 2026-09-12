# Analytics methodology

> **This is a product-defined model, not a scientifically validated one.** The
> weights, windows, and thresholds below were chosen to be simple, deterministic,
> and explainable — not derived from educational-measurement research. Treat
> every number this system produces as a heuristic signal for a teacher to
> investigate, never as a certified measurement of a student's ability.
>
> **Attendance and performance are never causally linked by this system.** Any
> UI or copy that shows both together must use observational language only
> ("students with higher attendance in this batch also show higher average
> scores"), never causal language ("attendance improves scores").

All the logic described here lives in `backend/app/services/analytics_service.py`.
Every number is **recomputed live from `responses`/`assessment_attempts` on every
API read** — `performance_snapshots` is a materialized cache written by a
recalculation job, never itself read by the API, so it can never be a source of
staleness bugs. See `compute_topic_performance()` for the single source of truth
all of the below is implemented in.

## Scope: only graded, finalized data counts

A response only enters any calculation below if:
- its parent attempt has `status` `SUBMITTED` or `EXPIRED` (not `IN_PROGRESS`), and
- `response.score` is not null (subjective SHORT_ANSWER/LONG_ANSWER responses are
  excluded entirely until a teacher grades them — an ungraded response is treated
  as "not yet data", not as a zero).

## Two granularities

- **Question-level** (every individual graded response, across every attempt):
  used for `accuracy` and `difficulty_adjusted_accuracy`. This is the most
  statistically sound granularity for a single "how well does this student know
  this topic overall" number.
- **Attempt-level** (one number per attempt — the topic-restricted score ratio
  for that attempt, i.e. `sum(score for that topic's questions in this attempt)
  / sum(marks for that topic's questions in this attempt)`): used for the
  recent/historical split, consistency, and trend. This matches the product
  spec's own worked example (§18: "Trigonometry: 41%, 46%, 52%, 61% → Improving")
  — one percentage per *test*, not per question — and matches §16's framing of
  consistency as "variation in performance... across attempts".

## Topic accuracy

```
accuracy = sum(response.score for all graded responses to this topic's questions)
         / sum(question.marks for those same responses)
```

## Recent vs. historical split

Not a calendar-time window — an **attempt-count window**
(`settings.analytics_recent_window`, default **3**), because the demo/seed data
doesn't naturally spread across real calendar days and a count-based window is
deterministic regardless of when tests happen to run:

- Build the chronological series of per-attempt topic ratios (oldest → newest).
- `recent` = the last `min(window, n)` attempts in that series.
- `historical` = every attempt **before** that window (non-overlapping with
  `recent`, to avoid double-counting recent performance in both terms of the
  mastery formula).
- **Fallback**: if a student has `n <= window` attempts on a topic, there is no
  "before the window" data yet — `historical_accuracy` falls back to equal
  `recent_accuracy` (documented here, not silently baked into a magic number).
  This means a brand-new topic doesn't get an artificially low or high mastery
  score just because it has no history yet.

Each of `recent_accuracy` / `historical_accuracy` is itself a **weighted** ratio
(`sum(scores in that slice) / sum(marks in that slice)`), not an average of
per-attempt percentages — this weights attempts with more topic-marks more
heavily, consistent with how `accuracy` itself is computed.

## Consistency score

`statistics.pstdev()` (population standard deviation, since we have the
student's *entire* known history for the topic, not a sample) of the per-attempt
ratio series:

```
consistency_score = max(0, 1 - 2 * pstdev(per_attempt_ratios)) * 100
```

Ratios are bounded to `[0, 1]`, so `pstdev` is bounded to `[0, 0.5]` (the
maximum spread — alternating 0s and 1s). The `* 2` scales that maximum spread to
a consistency score of exactly `0`; a perfectly consistent student (`pstdev = 0`,
including the trivial single-attempt case) scores `100`.

## Difficulty-adjusted accuracy

`Question.difficulty` is a free-text column. Recognized values are weighted:

| Difficulty | Weight |
|---|---|
| EASY (or unrecognized/null) | 1.0 |
| MEDIUM | 1.5 |
| HARD | 2.0 |

```
difficulty_adjusted_accuracy = sum(score * weight for each graded response)
                              / sum(marks * weight for each graded response)
```

This is a **weighted re-average** across questions by difficulty, not a bonus
added on top of accuracy — a student who does well specifically on HARD
questions will see `difficulty_adjusted_accuracy > accuracy`; one who does
comparatively worse on HARD questions sees the opposite. See
`test_difficulty_adjustment_rewards_hard_questions` for a worked example.

## Trend detection

Deterministic, reuses the recent/historical split above (not a separate
calculation):

- **`insufficient-data`** if the student has fewer than 2 attempts on the topic,
  **or** there is no historical slice yet (all attempts fall inside the recent
  window — no baseline to compare against).
- Otherwise, `delta = recent_accuracy - historical_accuracy`:
  - `delta > analytics_trend_threshold` (default **0.05**, i.e. 5 percentage
    points) → **`improving`**
  - `delta < -analytics_trend_threshold` → **`declining`**
  - otherwise → **`stable`**

## Mastery score (product spec §17)

```
mastery = 100 * (
    0.40 * recent_accuracy
  + 0.30 * historical_accuracy
  + 0.20 * difficulty_adjusted_accuracy
  + 0.10 * (consistency_score / 100)
)
```

clamped to `[0, 100]`. The four weights are **config values**
(`Settings.mastery_weight_recent/historical/difficulty_adjusted/consistency`
in `app/core/config.py`), not literals in the formula — change them via
environment variables without touching code.

### Category bands

| Score range | Category |
|---|---|
| 90 – 100 | Mastered |
| 75 – 89 | Strong |
| 60 – 74 | Developing |
| 40 – 59 | Needs Improvement |
| 0 – 39 | Critical |

## Worked example

(Matches `test_mastery_formula_worked_example` exactly — re-run that test after
touching any formula above to confirm the numbers still hold.)

A student takes four separate assessments over time, each with one 10-mark
question tagged to "Trigonometry", difficulty EASY throughout, scoring
**4, 5, 6, 8** out of 10 in that chronological order (`analytics_recent_window = 3`):

- `accuracy` = (4+5+6+8) / 40 = **57.5%**
- `recent` (last 3: 5,6,8) = (5+6+8) / 30 = **63.33%**
- `historical` (before that: just the 4) = 4/10 = **40.0%**
- `difficulty_adjusted_accuracy` = 57.5% (uniform EASY weight → identical to `accuracy`)
- `consistency_score`: ratios `[0.4, 0.5, 0.6, 0.8]`, mean 0.575, `pstdev ≈ 0.1479`
  → `(1 - 2×0.1479) × 100 ≈` **70.42**
- `mastery` = 100 × (0.4×0.6333 + 0.3×0.4 + 0.2×0.575 + 0.1×0.7042) ≈ **55.88**
  → category **"Needs Improvement"**
- `trend`: delta = 63.33% − 40.0% = +23.33pp > 5pp threshold → **`improving`**

## Overall student mastery, strengths, weak topics

`GET /students/{id}/performance` computes the above per topic for every topic
the student has any graded data in, then:

- `overall_mastery` = unweighted mean of every topic's `mastery_score` (a
  simple, easily-explained default — a student who is Strong in three topics
  and Critical in one gets pulled down proportionally, not swamped by whichever
  topic has the most questions).
- `strengths` = topics with `mastery_score >= 75` (Strong or Mastered).
- `weak_topics` = topics with `mastery_score < 60` (Needs Improvement or Critical).

## Attendance

`present_days` counts both `PRESENT` and `LATE` status days — a late arrival
still attended, just tardily. `attendance_percentage = present_days / total_marked_days * 100`,
`null` if no days have been marked yet (not `0`, to distinguish "no data" from
"zero attendance").

## Recalculation job

`recalculate_topic()` persists a `compute_topic_performance()` result into
`performance_snapshots`. It's triggered via FastAPI's `BackgroundTasks` after an
attempt is finalized and after a teacher grades a subjective response — **not**
Celery/RQ yet. Docker/Redis aren't available in this environment (see
`docs/PROGRESS.md`), so wiring an actual broker can't even be tested end-to-end
right now. `BackgroundTasks` gives the same user-visible guarantee the spec asks
for ("don't block the HTTP request that triggers it") without infrastructure
this phase can't verify. The call site (`analytics_service.recalculate_after_attempt`)
is the seam to swap for a real Celery task later — nothing else changes.
