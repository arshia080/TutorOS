"""Performance analytics: topic accuracy, mastery, trend, and attendance.

See docs/analytics.md for the full methodology writeup. Summary:

- All accuracy figures are computed fresh from `responses`/`assessment_attempts`
  on every read (see compute_topic_performance). `performance_snapshots` is a
  materialized cache written by recalculate_topic() -- it is never itself read
  by the live API, so it can never be a source of staleness bugs.
- "Recent" vs "historical" is an attempt-count window (settings.analytics_recent_window,
  default 3), not a calendar-time window -- deterministic regardless of how the
  demo data's timestamps happen to be spread out.
- Mastery weights and the recent-window/trend-threshold constants are config
  values (app/core/config.py), not literals buried in this file.
"""

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import date as date_
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import app.db.session as db_session_module
from app.core.config import settings
from app.models.analytics import Attendance, AttendanceStatus, PerformanceSnapshot, TrendDirection
from app.models.assessment import Assessment, AssessmentAttempt, AttemptStatus, Question, Response
from app.models.batch import Batch, BatchStudent, BatchStudentStatus
from app.models.subject import Topic
from app.models.user import User

# Difficulty is a free-text column (see Question.difficulty); unrecognized or
# missing values fall back to weight 1.0 (i.e. treated as EASY).
DIFFICULTY_WEIGHTS = {"EASY": 1.0, "MEDIUM": 1.5, "HARD": 2.0}

# Mastery category bands, spec section 17. Lower bound inclusive.
MASTERY_BANDS = [
    (90, "Mastered"),
    (75, "Strong"),
    (60, "Developing"),
    (40, "Needs Improvement"),
    (0, "Critical"),
]


def mastery_category(score: float) -> str:
    for lower_bound, label in MASTERY_BANDS:
        if score >= lower_bound:
            return label
    return "Critical"


@dataclass
class TopicPerformance:
    topic_id: uuid.UUID
    topic_name: str
    questions_attempted: int
    accuracy: float
    recent_accuracy: float
    historical_accuracy: float
    difficulty_adjusted_accuracy: float
    consistency_score: float
    mastery_score: float
    mastery_category: str
    trend: TrendDirection


@dataclass
class _AttemptTopicSlice:
    submitted_at: datetime
    score_sum: float
    marks_sum: float

    @property
    def ratio(self) -> float:
        return self.score_sum / self.marks_sum if self.marks_sum else 0.0


def _weighted_ratio(slices: list[_AttemptTopicSlice]) -> float:
    marks = sum(s.marks_sum for s in slices)
    if marks == 0:
        return 0.0
    return sum(s.score_sum for s in slices) / marks


def compute_topic_performance(db: Session, student_id: uuid.UUID, topic_id: uuid.UUID) -> TopicPerformance | None:
    """Recomputed live from graded responses. Returns None if the student has no
    graded (score is not null) responses to questions of this topic in a
    finalized attempt -- i.e. genuinely no data, not a zero score.
    """
    topic = db.get(Topic, topic_id)
    if topic is None:
        return None

    rows = (
        db.query(Response, Question, AssessmentAttempt)
        .join(Question, Question.id == Response.question_id)
        .join(AssessmentAttempt, AssessmentAttempt.id == Response.attempt_id)
        .filter(
            Question.topic_id == topic_id,
            AssessmentAttempt.student_id == student_id,
            AssessmentAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
            Response.score.isnot(None),
        )
        .all()
    )

    if not rows:
        return None

    # Question-level: overall accuracy and difficulty-adjusted accuracy use every
    # graded response individually (finest granularity, most statistically sound).
    total_score = sum(r.score for r, _q, _a in rows)
    total_marks = sum(q.marks for _r, q, _a in rows)
    accuracy = total_score / total_marks if total_marks else 0.0

    weighted_score = 0.0
    weighted_marks = 0.0
    for r, q, _a in rows:
        w = DIFFICULTY_WEIGHTS.get((q.difficulty or "").upper(), 1.0)
        weighted_score += r.score * w
        weighted_marks += q.marks * w
    difficulty_adjusted_accuracy = weighted_score / weighted_marks if weighted_marks else 0.0

    # Attempt-level: recent/historical split, consistency, and trend are all
    # computed over one ratio PER ATTEMPT (spec's own worked examples -- e.g.
    # "test1: 41%, test2: 46%..." -- are one number per test, not per question;
    # consistency is explicitly "variation ... across attempts").
    by_attempt: dict[uuid.UUID, _AttemptTopicSlice] = {}
    for r, q, a in rows:
        slice_ = by_attempt.get(a.id)
        submitted_at = a.submitted_at or a.started_at
        if slice_ is None:
            by_attempt[a.id] = _AttemptTopicSlice(submitted_at=submitted_at, score_sum=r.score, marks_sum=q.marks)
        else:
            slice_.score_sum += r.score
            slice_.marks_sum += q.marks

    series = sorted(by_attempt.values(), key=lambda s: s.submitted_at)
    window = settings.analytics_recent_window
    recent_slice = series[-window:]
    historical_slice = series[:-window] if len(series) > window else []

    recent_accuracy = _weighted_ratio(recent_slice)
    historical_accuracy = _weighted_ratio(historical_slice) if historical_slice else recent_accuracy

    ratios = [s.ratio for s in series]
    consistency_score = max(0.0, 1.0 - 2 * statistics.pstdev(ratios)) * 100 if len(ratios) >= 1 else 100.0

    if len(series) < 2 or not historical_slice:
        trend = TrendDirection.INSUFFICIENT_DATA
    else:
        delta = recent_accuracy - historical_accuracy
        if delta > settings.analytics_trend_threshold:
            trend = TrendDirection.IMPROVING
        elif delta < -settings.analytics_trend_threshold:
            trend = TrendDirection.DECLINING
        else:
            trend = TrendDirection.STABLE

    mastery = 100 * (
        settings.mastery_weight_recent * recent_accuracy
        + settings.mastery_weight_historical * historical_accuracy
        + settings.mastery_weight_difficulty_adjusted * difficulty_adjusted_accuracy
        + settings.mastery_weight_consistency * (consistency_score / 100)
    )
    mastery = max(0.0, min(100.0, mastery))

    return TopicPerformance(
        topic_id=topic_id,
        topic_name=topic.name,
        questions_attempted=len(rows),
        accuracy=round(accuracy * 100, 2),
        recent_accuracy=round(recent_accuracy * 100, 2),
        historical_accuracy=round(historical_accuracy * 100, 2),
        difficulty_adjusted_accuracy=round(difficulty_adjusted_accuracy * 100, 2),
        consistency_score=round(consistency_score, 2),
        mastery_score=round(mastery, 2),
        mastery_category=mastery_category(mastery),
        trend=trend,
    )


def list_topics_with_data(db: Session, student_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(Question.topic_id)
        .join(Response, Response.question_id == Question.id)
        .join(AssessmentAttempt, AssessmentAttempt.id == Response.attempt_id)
        .filter(
            AssessmentAttempt.student_id == student_id,
            AssessmentAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
            Response.score.isnot(None),
            Question.topic_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


@dataclass
class StudentPerformanceSummary:
    student_id: uuid.UUID
    overall_mastery: float
    topics: list[TopicPerformance] = field(default_factory=list)
    strengths: list[TopicPerformance] = field(default_factory=list)
    weak_topics: list[TopicPerformance] = field(default_factory=list)


def compute_student_performance(db: Session, student_id: uuid.UUID) -> StudentPerformanceSummary:
    topic_ids = list_topics_with_data(db, student_id)
    topics = [compute_topic_performance(db, student_id, tid) for tid in topic_ids]
    topics = [t for t in topics if t is not None]
    topics.sort(key=lambda t: t.mastery_score)

    overall_mastery = round(sum(t.mastery_score for t in topics) / len(topics), 2) if topics else 0.0
    strengths = [t for t in topics if t.mastery_score >= 75]
    weak = [t for t in topics if t.mastery_score < 60]

    return StudentPerformanceSummary(
        student_id=student_id, overall_mastery=overall_mastery, topics=topics, strengths=strengths, weak_topics=weak
    )


def recalculate_topic(db: Session, student_id: uuid.UUID, topic_id: uuid.UUID) -> None:
    """Persist compute_topic_performance()'s result into performance_snapshots.
    Called from a FastAPI BackgroundTask so it never blocks the triggering
    request (see docs/analytics.md for why this isn't Celery yet).
    """
    perf = compute_topic_performance(db, student_id, topic_id)
    if perf is None:
        return

    snapshot = (
        db.query(PerformanceSnapshot)
        .filter(PerformanceSnapshot.student_id == student_id, PerformanceSnapshot.topic_id == topic_id)
        .first()
    )
    if snapshot is None:
        snapshot = PerformanceSnapshot(student_id=student_id, topic_id=topic_id)
        db.add(snapshot)

    snapshot.mastery_score = perf.mastery_score
    snapshot.mastery_category = perf.mastery_category
    snapshot.accuracy = perf.accuracy
    snapshot.recent_accuracy = perf.recent_accuracy
    snapshot.historical_accuracy = perf.historical_accuracy
    snapshot.difficulty_adjusted_accuracy = perf.difficulty_adjusted_accuracy
    snapshot.consistency_score = perf.consistency_score
    snapshot.trend = perf.trend
    snapshot.questions_attempted = perf.questions_attempted
    db.commit()


def topics_touched_by_assessment(db: Session, assessment_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(Question.topic_id)
        .filter(Question.assessment_id == assessment_id, Question.topic_id.isnot(None))
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def recalculate_after_attempt(student_id: uuid.UUID, topic_ids: list[uuid.UUID]) -> None:
    """Entry point for a BackgroundTask: opens its own DB session, independent of
    the request's session (which may already be closed by the time this runs).

    Looked up via the module (not imported directly as a name) so tests can
    point `app.db.session.SessionLocal` at their isolated test engine and have
    this pick it up -- a plain `from app.db.session import SessionLocal` would
    bind to the production engine at import time and never see that override.
    """
    db = db_session_module.SessionLocal()
    try:
        for topic_id in topic_ids:
            recalculate_topic(db, student_id, topic_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


def mark_attendance(db: Session, batch_id: uuid.UUID, day: date_, records: list[tuple[uuid.UUID, AttendanceStatus]]) -> None:
    for student_id, status_value in records:
        row = (
            db.query(Attendance)
            .filter(Attendance.batch_id == batch_id, Attendance.student_id == student_id, Attendance.date == day)
            .first()
        )
        if row is None:
            row = Attendance(batch_id=batch_id, student_id=student_id, date=day)
            db.add(row)
        row.status = status_value
    db.commit()


def get_attendance_for_date(db: Session, batch_id: uuid.UUID, day: date_) -> list[Attendance]:
    return db.query(Attendance).filter(Attendance.batch_id == batch_id, Attendance.date == day).all()


def student_attendance_percentage(db: Session, student_id: uuid.UUID, batch_id: uuid.UUID | None = None) -> dict:
    query = db.query(Attendance).filter(Attendance.student_id == student_id)
    if batch_id is not None:
        query = query.filter(Attendance.batch_id == batch_id)
    records = query.order_by(Attendance.date).all()

    total = len(records)
    # A late arrival still attended -- counted as present for the percentage.
    present = sum(1 for r in records if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
    percentage = round(present / total * 100, 2) if total else None

    return {
        "student_id": student_id,
        "total_days": total,
        "present_days": present,
        "attendance_percentage": percentage,
        "records": records,
    }


def batch_average_attendance(db: Session, batch_id: uuid.UUID) -> float | None:
    student_ids = [
        row[0]
        for row in db.query(BatchStudent.student_id)
        .filter(BatchStudent.batch_id == batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .all()
    ]
    if not student_ids:
        return None
    percentages = []
    for sid in student_ids:
        result = student_attendance_percentage(db, sid, batch_id)
        if result["attendance_percentage"] is not None:
            percentages.append(result["attendance_percentage"])
    return round(sum(percentages) / len(percentages), 2) if percentages else None


# ---------------------------------------------------------------------------
# Class / attention panel analytics
# ---------------------------------------------------------------------------


def attention_panel(db: Session, batch_id: uuid.UUID) -> list[dict]:
    """One row per active student: their single weakest topic and its trend --
    exactly the section 9 "Student attention panel" shape.
    """
    student_ids = [
        row[0]
        for row in db.query(BatchStudent.student_id)
        .filter(BatchStudent.batch_id == batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .all()
    ]

    rows = []
    for sid in student_ids:
        student = db.get(User, sid)
        topic_ids = list_topics_with_data(db, sid)
        topic_perfs = [compute_topic_performance(db, sid, tid) for tid in topic_ids]
        topic_perfs = [t for t in topic_perfs if t is not None]
        if not topic_perfs:
            continue
        weakest = min(topic_perfs, key=lambda t: t.mastery_score)
        rows.append(
            {
                "student_id": sid,
                "student_name": student.name,
                "topic_id": weakest.topic_id,
                "topic_name": weakest.topic_name,
                "mastery_score": weakest.mastery_score,
                "trend": weakest.trend,
            }
        )
    rows.sort(key=lambda r: r["mastery_score"])
    return rows


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = fraction * (len(sorted_values) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = idx - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _distribution(values: list[float]) -> dict[str, int]:
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for v in values:
        if v < 20:
            buckets["0-20"] += 1
        elif v < 40:
            buckets["20-40"] += 1
        elif v < 60:
            buckets["40-60"] += 1
        elif v < 80:
            buckets["60-80"] += 1
        else:
            buckets["80-100"] += 1
    return buckets


def class_performance(db: Session, batch_id: uuid.UUID) -> dict:
    normalized_scores = [
        row[0] * 100.0 / row[1]
        for row in db.query(AssessmentAttempt.total_score, Assessment.total_marks)
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(
            Assessment.batch_id == batch_id,
            AssessmentAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
            AssessmentAttempt.total_score.isnot(None),
        )
        .all()
        if row[1]
    ]
    normalized_scores.sort()

    student_ids = [
        row[0]
        for row in db.query(BatchStudent.student_id)
        .filter(BatchStudent.batch_id == batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .all()
    ]
    topic_ids = set()
    for sid in student_ids:
        topic_ids.update(list_topics_with_data(db, sid))

    topics_summary = []
    for tid in topic_ids:
        masteries = []
        topic_name = None
        for sid in student_ids:
            perf = compute_topic_performance(db, sid, tid)
            if perf is not None:
                masteries.append(perf.mastery_score)
                topic_name = perf.topic_name
        if not masteries:
            continue
        masteries.sort()
        topics_summary.append(
            {
                "topic_id": tid,
                "topic_name": topic_name,
                "average_mastery": round(sum(masteries) / len(masteries), 2),
                "median_mastery": round(_percentile(masteries, 0.5), 2),
                "high_mastery": max(masteries),
                "low_mastery": min(masteries),
                "student_count": len(masteries),
            }
        )
    topics_summary.sort(key=lambda t: t["average_mastery"])

    average_mastery = (
        round(sum(t["average_mastery"] for t in topics_summary) / len(topics_summary), 2) if topics_summary else 0.0
    )

    return {
        "average_score": round(sum(normalized_scores) / len(normalized_scores), 2) if normalized_scores else None,
        "median_score": round(_percentile(normalized_scores, 0.5), 2) if normalized_scores else None,
        "high_score": round(normalized_scores[-1], 2) if normalized_scores else None,
        "low_score": round(normalized_scores[0], 2) if normalized_scores else None,
        "score_distribution": _distribution(normalized_scores),
        "average_attendance_percentage": batch_average_attendance(db, batch_id),
        "average_mastery": average_mastery,
        "topics": topics_summary,
    }


def question_analytics(db: Session, assessment_id: uuid.UUID) -> list[dict]:
    questions = db.query(Question).filter(Question.assessment_id == assessment_id).order_by(Question.order_index).all()
    result = []
    for q in questions:
        responses = (
            db.query(Response)
            .join(AssessmentAttempt, AssessmentAttempt.id == Response.attempt_id)
            .filter(
                Response.question_id == q.id,
                AssessmentAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
            )
            .all()
        )
        graded = [r for r in responses if r.is_correct is not None]
        percent_correct = round(sum(1 for r in graded if r.is_correct) / len(graded) * 100, 2) if graded else None
        times = [r.time_spent_seconds for r in responses if r.time_spent_seconds is not None]
        avg_time = round(sum(times) / len(times), 2) if times else None
        result.append(
            {
                "question_id": q.id,
                "question_text": q.question_text,
                "attempts": len(responses),
                "percent_correct": percent_correct,
                "avg_time_seconds": avg_time,
            }
        )
    return result
