"""Analytics correctness tests.

Topic accuracy / mastery / trend are tested by inserting AssessmentAttempt +
Question + Response rows directly (bypassing the HTTP attempt flow, which is
already covered in test_attempts.py) so each test has exact, hand-computed
control over scores, marks, difficulty, and timestamps.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.analytics import PerformanceSnapshot, TrendDirection
from app.models.assessment import (
    Assessment,
    AssessmentAttempt,
    AssessmentStatus,
    AttemptStatus,
    Question,
    QuestionType,
    Response,
)
from app.models.subject import Subject, Topic
from app.services import analytics_service
from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _make_topic(db_session, name="Trigonometry") -> Topic:
    subject = Subject(name="Mathematics", grade="10")
    db_session.add(subject)
    db_session.flush()
    topic = Topic(subject_id=subject.id, name=name)
    db_session.add(topic)
    db_session.flush()
    return topic


def _make_student(db_session) -> uuid.UUID:
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    student = User(name="Rahul Sharma", email=f"{uuid.uuid4().hex}@test.com", password_hash=hash_password("x"), role=UserRole.STUDENT)
    db_session.add(student)
    db_session.flush()
    return student.id


def _make_dummy_batch_and_teacher(db_session):
    from app.core.security import hash_password
    from app.models.batch import Batch
    from app.models.user import User, UserRole

    teacher = User(name="T", email=f"{uuid.uuid4().hex}@test.com", password_hash=hash_password("x"), role=UserRole.TEACHER)
    db_session.add(teacher)
    db_session.flush()
    batch = Batch(teacher_id=teacher.id, name="Batch")
    db_session.add(batch)
    db_session.flush()
    return teacher.id, batch.id


def _add_attempt_with_topic_question(
    db_session, student_id, topic_id, teacher_id, batch_id, marks, score, difficulty, submitted_at
):
    assessment = Assessment(
        teacher_id=teacher_id,
        batch_id=batch_id,
        subject_id=db_session.get(Topic, topic_id).subject_id,
        title="Quiz",
        duration_minutes=10,
        total_marks=marks,
        status=AssessmentStatus.PUBLISHED,
    )
    db_session.add(assessment)
    db_session.flush()

    question = Question(
        assessment_id=assessment.id,
        question_text="Q",
        question_type=QuestionType.SHORT_ANSWER,
        topic_id=topic_id,
        difficulty=difficulty,
        marks=marks,
    )
    db_session.add(question)
    db_session.flush()

    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        student_id=student_id,
        started_at=submitted_at - timedelta(minutes=5),
        submitted_at=submitted_at,
        status=AttemptStatus.SUBMITTED,
        total_score=score,
    )
    db_session.add(attempt)
    db_session.flush()

    response = Response(attempt_id=attempt.id, question_id=question.id, score=score, is_correct=score >= marks)
    db_session.add(response)
    db_session.commit()
    return assessment, question, attempt


def test_topic_accuracy_hand_computed(db_session):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)

    # Two attempts on this topic: 3/10 and 7/10 -> accuracy should be exactly 10/20 = 50%.
    _add_attempt_with_topic_question(db_session, student_id, topic.id, teacher_id, batch_id, 10, 3, "EASY", now - timedelta(days=2))
    _add_attempt_with_topic_question(db_session, student_id, topic.id, teacher_id, batch_id, 10, 7, "EASY", now - timedelta(days=1))

    perf = analytics_service.compute_topic_performance(db_session, student_id, topic.id)
    assert perf.accuracy == pytest.approx(50.0)
    assert perf.questions_attempted == 2


def test_mastery_formula_worked_example(db_session):
    """Matches the worked example in docs/analytics.md: four attempts scoring
    4, 5, 6, 8 out of 10 (ratios 0.4, 0.5, 0.6, 0.8), all EASY difficulty.
    """
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)

    scores = [4, 5, 6, 8]
    for i, score in enumerate(scores):
        _add_attempt_with_topic_question(
            db_session, student_id, topic.id, teacher_id, batch_id, 10, score, "EASY", now - timedelta(days=4 - i)
        )

    perf = analytics_service.compute_topic_performance(db_session, student_id, topic.id)

    # Hand-computed with RECENT_WINDOW=3 (default): recent = last 3 attempts (5,6,8)/30,
    # historical = attempt before that (4)/10.
    assert perf.accuracy == pytest.approx(57.5)
    assert perf.recent_accuracy == pytest.approx(63.33, abs=0.01)
    assert perf.historical_accuracy == pytest.approx(40.0)
    assert perf.difficulty_adjusted_accuracy == pytest.approx(57.5)  # uniform EASY weight -> same as accuracy
    assert perf.consistency_score == pytest.approx(70.42, abs=0.01)
    assert perf.mastery_score == pytest.approx(55.88, abs=0.01)
    assert perf.mastery_category == "Needs Improvement"
    assert perf.trend == TrendDirection.IMPROVING


def test_mastery_category_bands(db_session):
    assert analytics_service.mastery_category(95) == "Mastered"
    assert analytics_service.mastery_category(90) == "Mastered"
    assert analytics_service.mastery_category(89.9) == "Strong"
    assert analytics_service.mastery_category(75) == "Strong"
    assert analytics_service.mastery_category(74.9) == "Developing"
    assert analytics_service.mastery_category(60) == "Developing"
    assert analytics_service.mastery_category(59.9) == "Needs Improvement"
    assert analytics_service.mastery_category(40) == "Needs Improvement"
    assert analytics_service.mastery_category(39.9) == "Critical"
    assert analytics_service.mastery_category(0) == "Critical"


def test_difficulty_adjustment_rewards_hard_questions(db_session):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)

    # One EASY question missed, one HARD question aced -- difficulty-adjusted
    # accuracy should be pulled up relative to the plain (unweighted) accuracy,
    # since the HARD question counts for more in both numerator and denominator.
    _add_attempt_with_topic_question(db_session, student_id, topic.id, teacher_id, batch_id, 10, 0, "EASY", now - timedelta(days=2))
    _add_attempt_with_topic_question(db_session, student_id, topic.id, teacher_id, batch_id, 10, 10, "HARD", now - timedelta(days=1))

    perf = analytics_service.compute_topic_performance(db_session, student_id, topic.id)
    plain_accuracy = 10 / 20 * 100  # 50%
    weighted_accuracy = (0 * 1.0 + 10 * 2.0) / (10 * 1.0 + 10 * 2.0) * 100  # 66.67%
    assert perf.accuracy == pytest.approx(plain_accuracy)
    assert perf.difficulty_adjusted_accuracy == pytest.approx(weighted_accuracy, abs=0.01)
    assert perf.difficulty_adjusted_accuracy > perf.accuracy


@pytest.mark.parametrize(
    "scores,expected_trend",
    [
        ([2, 3, 8, 9, 9], TrendDirection.IMPROVING),
        ([9, 9, 8, 3, 2], TrendDirection.DECLINING),
        ([7, 7, 7, 7, 7], TrendDirection.STABLE),
        ([7, 8], TrendDirection.INSUFFICIENT_DATA),
        ([7], TrendDirection.INSUFFICIENT_DATA),
    ],
)
def test_trend_detection_synthetic_sequences(db_session, scores, expected_trend):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)

    for i, score in enumerate(scores):
        _add_attempt_with_topic_question(
            db_session, student_id, topic.id, teacher_id, batch_id, 10, score, "EASY", now - timedelta(days=len(scores) - i)
        )

    perf = analytics_service.compute_topic_performance(db_session, student_id, topic.id)
    assert perf.trend == expected_trend


def test_no_data_returns_none(db_session):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    assert analytics_service.compute_topic_performance(db_session, student_id, topic.id) is None


def test_ungraded_response_excluded_from_accuracy(db_session):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)

    assessment = Assessment(
        teacher_id=teacher_id, batch_id=batch_id, subject_id=topic.subject_id, title="Quiz",
        duration_minutes=10, total_marks=10, status=AssessmentStatus.PUBLISHED,
    )
    db_session.add(assessment)
    db_session.flush()
    question = Question(
        assessment_id=assessment.id, question_text="Explain", question_type=QuestionType.SHORT_ANSWER,
        topic_id=topic.id, marks=10,
    )
    db_session.add(question)
    db_session.flush()
    attempt = AssessmentAttempt(
        assessment_id=assessment.id, student_id=student_id, started_at=now, submitted_at=now,
        status=AttemptStatus.SUBMITTED, total_score=0,
    )
    db_session.add(attempt)
    db_session.flush()
    # Ungraded subjective response: score is None.
    db_session.add(Response(attempt_id=attempt.id, question_id=question.id, score=None, is_correct=None, response_text="..."))
    db_session.commit()

    assert analytics_service.compute_topic_performance(db_session, student_id, topic.id) is None


def test_recalculate_topic_persists_snapshot(db_session):
    topic = _make_topic(db_session)
    student_id = _make_student(db_session)
    teacher_id, batch_id = _make_dummy_batch_and_teacher(db_session)
    now = datetime.now(timezone.utc)
    _add_attempt_with_topic_question(db_session, student_id, topic.id, teacher_id, batch_id, 10, 8, "MEDIUM", now)

    analytics_service.recalculate_topic(db_session, student_id, topic.id)

    snapshot = (
        db_session.query(PerformanceSnapshot)
        .filter(PerformanceSnapshot.student_id == student_id, PerformanceSnapshot.topic_id == topic.id)
        .first()
    )
    assert snapshot is not None
    assert snapshot.accuracy == pytest.approx(80.0)

    # Recalculating again should update the same row, not create a duplicate.
    analytics_service.recalculate_topic(db_session, student_id, topic.id)
    count = (
        db_session.query(PerformanceSnapshot)
        .filter(PerformanceSnapshot.student_id == student_id, PerformanceSnapshot.topic_id == topic.id)
        .count()
    )
    assert count == 1


def test_submit_attempt_triggers_background_recalculation(client, db_session):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    topic = client.post(
        "/topics", json={"subject_id": subject["id"], "name": "Trigonometry"}, headers=auth_headers(token)
    ).json()

    student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )

    assessment = client.post(
        "/assessments",
        json={"batch_id": batch["id"], "subject_id": subject["id"], "title": "Quiz", "duration_minutes": 10, "total_marks": 2},
        headers=auth_headers(token),
    ).json()
    client.post(
        f"/assessments/{assessment['id']}/questions",
        json={
            "question_text": "2+2?",
            "question_type": "MCQ",
            "topic_id": topic["id"],
            "marks": 2,
            "options": [{"option_text": "4", "is_correct": True}, {"option_text": "5", "is_correct": False}],
        },
        headers=auth_headers(token),
    )
    client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))

    headers = auth_headers(student["access_token"])
    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    option_id = next(o["id"] for o in start["questions"][0]["options"] if o["option_text"] == "4")
    client.post(
        f"/attempts/{start['id']}/responses",
        json={"question_id": start["questions"][0]["id"], "selected_option_ids": [option_id]},
        headers=headers,
    )
    client.post(f"/attempts/{start['id']}/submit", headers=headers)

    snapshot = (
        db_session.query(PerformanceSnapshot)
        .filter(PerformanceSnapshot.topic_id == uuid.UUID(topic["id"]))
        .first()
    )
    assert snapshot is not None
    assert snapshot.accuracy == pytest.approx(100.0)
