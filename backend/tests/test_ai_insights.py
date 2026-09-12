from datetime import datetime, timezone

from app.models.assessment import Assessment, AssessmentAttempt, AssessmentStatus, AttemptStatus, Question, QuestionType, Response
from app.models.subject import Subject, Topic
from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _seed_topic_performance(db_session, client, token, batch_id, student_id):
    import uuid as uuid_module

    teacher_id = uuid_module.UUID(client.get("/auth/me", headers=auth_headers(token)).json()["id"])

    subject = Subject(name="Mathematics", grade="10")
    db_session.add(subject)
    db_session.flush()
    topic = Topic(subject_id=subject.id, name="Trigonometry")
    db_session.add(topic)
    db_session.flush()

    assessment = Assessment(
        teacher_id=teacher_id,
        batch_id=uuid_module.UUID(batch_id),
        subject_id=subject.id,
        title="Quiz",
        duration_minutes=10,
        total_marks=10,
        status=AssessmentStatus.PUBLISHED,
    )
    db_session.add(assessment)
    db_session.flush()
    question = Question(
        assessment_id=assessment.id, question_text="Q", question_type=QuestionType.SHORT_ANSWER,
        topic_id=topic.id, marks=10,
    )
    db_session.add(question)
    db_session.flush()
    now = datetime.now(timezone.utc)
    attempt = AssessmentAttempt(
        assessment_id=assessment.id, student_id=uuid_module.UUID(student_id), started_at=now, submitted_at=now,
        status=AttemptStatus.SUBMITTED, total_score=8,
    )
    db_session.add(attempt)
    db_session.flush()
    db_session.add(Response(attempt_id=attempt.id, question_id=question.id, score=8, is_correct=True))
    db_session.commit()
    return topic.id


def test_grounded_insight_returned(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch['id']}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=auth_headers(token)
    )
    topic_id = _seed_topic_performance(db_session, client, token, batch["id"], student["user"]["id"])

    fake_ai_provider.text_responses = ["Rahul is doing well at 80% accuracy on this topic, showing mastery."]

    response = client.get(
        f"/ai/students/{student['user']['id']}/topics/{topic_id}/insight", headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    assert "insight" in response.json()


def test_fabricated_numbers_rejected_after_retries(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch['id']}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=auth_headers(token)
    )
    topic_id = _seed_topic_performance(db_session, client, token, batch["id"], student["user"]["id"])

    fake_ai_provider.text_responses = [
        "Rahul improved by 47% over his last 12 attempts, a remarkable jump.",
        "He's now scoring 999% which is unprecedented.",
    ]

    response = client.get(
        f"/ai/students/{student['user']['id']}/topics/{topic_id}/insight", headers=auth_headers(token)
    )
    assert response.status_code == 502


def test_student_cannot_view_another_students_insight(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch['id']}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=auth_headers(token)
    )
    topic_id = _seed_topic_performance(db_session, client, token, batch["id"], student["user"]["id"])

    outsider = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.get(
        f"/ai/students/{student['user']['id']}/topics/{topic_id}/insight", headers=auth_headers(outsider["access_token"])
    )
    assert response.status_code == 404


def test_no_performance_data_returns_404(client, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    topic = client.post("/topics", json={"subject_id": subject["id"], "name": "Algebra"}, headers=auth_headers(token)).json()
    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch['id']}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=auth_headers(token)
    )

    response = client.get(
        f"/ai/students/{student['user']['id']}/topics/{topic['id']}/insight", headers=auth_headers(token)
    )
    assert response.status_code == 404
