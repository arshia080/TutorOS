from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models.assessment import Assessment, AssessmentAttempt, AssessmentStatus, AttemptStatus, Question, QuestionType, Response
from app.models.practice import Recommendation, RecommendationStatus
from app.models.subject import Subject, Topic
from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _seed_weak_topic(db_session, client, token, batch_id, student_id, mastery_ratio=0.4):
    """Gives the student one graded response on a fresh topic, at roughly the
    given accuracy ratio (used both as accuracy and as the mastery driver,
    since with a single attempt recent==historical==accuracy).
    """
    import uuid as uuid_module

    teacher_id = uuid_module.UUID(client.get("/auth/me", headers=auth_headers(token)).json()["id"])

    subject = Subject(name="Mathematics", grade="10")
    db_session.add(subject)
    db_session.flush()
    topic = Topic(subject_id=subject.id, name="Trigonometry")
    db_session.add(topic)
    db_session.flush()

    assessment = Assessment(
        teacher_id=teacher_id, batch_id=uuid_module.UUID(batch_id), subject_id=subject.id, title="Quiz",
        duration_minutes=10, total_marks=10, status=AssessmentStatus.PUBLISHED,
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
        status=AttemptStatus.SUBMITTED, total_score=mastery_ratio * 10,
    )
    db_session.add(attempt)
    db_session.flush()
    db_session.add(Response(attempt_id=attempt.id, question_id=question.id, score=mastery_ratio * 10, is_correct=mastery_ratio >= 1))
    db_session.commit()
    return topic.id


def _enrolled_student(client, token, batch_id):
    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch_id}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=auth_headers(token)
    )
    return student


def _practice_set(easy_texts, medium_texts, hard_texts):
    questions = []
    for text in easy_texts:
        questions.append({
            "question_text": text, "question_type": "MCQ", "difficulty": "EASY", "marks": 1,
            "options": [{"option_text": "A", "is_correct": True}, {"option_text": "B", "is_correct": False}],
        })
    for text in medium_texts:
        questions.append({
            "question_text": text, "question_type": "TRUE_FALSE", "difficulty": "MEDIUM", "marks": 1,
            "options": [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
        })
    for text in hard_texts:
        questions.append({
            "question_text": text, "question_type": "NUMERICAL", "difficulty": "HARD", "marks": 1,
            "options": [{"option_text": "42", "is_correct": True}],
        })
    return {"questions": questions}


def test_weak_topic_below_threshold_appears_in_weak_topics(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "weak_topic_mastery_threshold", 60.0)
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"], mastery_ratio=0.4)

    perf = client.get(f"/students/{student['user']['id']}/performance", headers=auth_headers(token)).json()
    assert len(perf["weak_topics"]) == 1
    assert perf["weak_topics"][0]["mastery_score"] < 60.0


def test_topic_above_threshold_not_weak(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "weak_topic_mastery_threshold", 60.0)
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"], mastery_ratio=1.0)

    perf = client.get(f"/students/{student['user']['id']}/performance", headers=auth_headers(token)).json()
    assert perf["weak_topics"] == []
    assert len(perf["strengths"]) == 1


def test_generate_practice_respects_difficulty_mix(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"])

    fake_ai_provider.structured_response = _practice_set(["e1", "e2"], ["m1"], ["h1"])
    response = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 2, "medium_count": 1, "hard_count": 1},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["questions"]) == 4
    difficulties = [q["difficulty"] for q in body["questions"]]
    assert difficulties.count("EASY") == 2
    assert difficulties.count("MEDIUM") == 1
    assert difficulties.count("HARD") == 1


def test_generate_practice_rejects_wrong_difficulty_mix(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"])

    # Asked for 2 easy, 1 medium, 1 hard -- AI returns 1 easy, 2 medium, 1 hard instead.
    fake_ai_provider.structured_response = _practice_set(["e1"], ["m1", "m2"], ["h1"])
    response = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 2, "medium_count": 1, "hard_count": 1},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 422
    errors = response.json()["error"]["message"]["errors"]
    assert any("EASY" in e for e in errors)


def test_generate_practice_rejects_disallowed_question_type(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"])

    data = _practice_set(["e1"], [], [])
    data["questions"][0]["question_type"] = "MULTI_SELECT"
    data["questions"][0]["options"].append({"option_text": "C", "is_correct": True})
    fake_ai_provider.structured_response = data

    response = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 1, "medium_count": 0, "hard_count": 0},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 422


def test_cannot_generate_practice_without_performance_data(client, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    topic = client.post("/topics", json={"subject_id": subject["id"], "name": "Algebra"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])

    response = client.post(
        f"/students/{student['user']['id']}/topics/{topic['id']}/practice",
        json={},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 404


def test_full_practice_flow_with_before_after_mastery(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"], mastery_ratio=0.4)
    headers = auth_headers(student["access_token"])

    fake_ai_provider.structured_response = _practice_set(["e1", "e2"], ["m1"], ["h1"])
    practice = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 2, "medium_count": 1, "hard_count": 1},
        headers=headers,
    ).json()

    mastery_before = practice["mastery_before"]
    assert mastery_before < 60  # seeded weak

    # Correct answers to every question.
    for q in practice["questions"]:
        if q["question_type"] == "NUMERICAL":
            payload = {"question_id": q["id"], "response_text": "42"}
        else:
            # is_correct is hidden while the set is IN_PROGRESS; the first option
            # is always the correct one by construction in _practice_set() above
            # (MCQ correct is "A", TRUE_FALSE correct is "True").
            correct_option = q["options"][0]["id"]
            payload = {"question_id": q["id"], "selected_option_id": correct_option}
        r = client.post(f"/practice-sets/{practice['id']}/responses", json=payload, headers=headers)
        assert r.status_code == 200, r.text

    completion = client.post(f"/practice-sets/{practice['id']}/complete", headers=headers)
    assert completion.status_code == 200, completion.text
    body = completion.json()
    assert body["mastery_before"] == mastery_before
    assert body["mastery_after"] > body["mastery_before"]
    assert body["delta"] == round(body["mastery_after"] - body["mastery_before"], 2)
    assert "observed change" in body["note"]
    assert all(r["is_correct"] for r in body["responses"])

    # Recommendation should now be marked completed.
    recommendation = db_session.query(Recommendation).filter(Recommendation.practice_set_id.isnot(None)).first()
    assert recommendation is not None
    assert recommendation.status == RecommendationStatus.COMPLETED


def test_cannot_complete_practice_with_no_answers(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"])
    headers = auth_headers(student["access_token"])

    fake_ai_provider.structured_response = _practice_set(["e1"], [], [])
    practice = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 1, "medium_count": 0, "hard_count": 0},
        headers=headers,
    ).json()

    response = client.post(f"/practice-sets/{practice['id']}/complete", headers=headers)
    assert response.status_code == 422


def test_completing_twice_is_idempotent(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student["user"]["id"])
    headers = auth_headers(student["access_token"])

    fake_ai_provider.structured_response = _practice_set(["e1"], [], [])
    practice = client.post(
        f"/students/{student['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 1, "medium_count": 0, "hard_count": 0},
        headers=headers,
    ).json()
    q = practice["questions"][0]
    client.post(
        f"/practice-sets/{practice['id']}/responses",
        json={"question_id": q["id"], "selected_option_id": q["options"][0]["id"]},
        headers=headers,
    )

    first = client.post(f"/practice-sets/{practice['id']}/complete", headers=headers).json()
    second = client.post(f"/practice-sets/{practice['id']}/complete", headers=headers).json()
    assert first["mastery_after"] == second["mastery_after"]


def test_student_cannot_access_another_students_practice_set(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student_a = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student_a["user"]["id"])

    fake_ai_provider.structured_response = _practice_set(["e1"], [], [])
    practice = client.post(
        f"/students/{student_a['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 1, "medium_count": 0, "hard_count": 0},
        headers=auth_headers(student_a["access_token"]),
    ).json()

    student_b = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.get(f"/practice-sets/{practice['id']}", headers=auth_headers(student_b["access_token"]))
    assert response.status_code == 404


def test_student_cannot_generate_practice_for_another_student(client, db_session, fake_ai_provider):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    student_a = _enrolled_student(client, token, batch["id"])
    topic_id = _seed_weak_topic(db_session, client, token, batch["id"], student_a["user"]["id"])

    student_b = register(client, "Ananya Gupta", "ananya@test.com")
    fake_ai_provider.structured_response = _practice_set(["e1"], [], [])
    response = client.post(
        f"/students/{student_a['user']['id']}/topics/{topic_id}/practice",
        json={"easy_count": 1, "medium_count": 0, "hard_count": 0},
        headers=auth_headers(student_b["access_token"]),
    )
    assert response.status_code == 403
