import uuid
from datetime import datetime, timedelta, timezone

from app.models.assessment import AssessmentAttempt
from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup_batch_subject(client, token):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    return batch, subject


def _enroll_student(client, token, batch_id, email="rahul@test.com", name="Rahul Sharma"):
    student = register(client, name, email)
    client.post(
        f"/batches/{batch_id}/students", json={"name": name, "email": email}, headers=auth_headers(token)
    )
    return student


def _build_full_assessment(client, token, batch_id, subject_id, duration_minutes=30):
    """One question of every type. Total marks: 2+3+1+2+2 = 10.
    MCQ correct = "4". MULTI_SELECT correct = {"A", "C"}. TRUE_FALSE correct = "True".
    NUMERICAL correct = 42.
    """
    assessment = client.post(
        "/assessments",
        json={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "title": "Full Test",
            "duration_minutes": duration_minutes,
            "total_marks": 10,
        },
        headers=auth_headers(token),
    ).json()

    def add(question_type, marks, options):
        return client.post(
            f"/assessments/{assessment['id']}/questions",
            json={"question_text": question_type, "question_type": question_type, "marks": marks, "options": options},
            headers=auth_headers(token),
        ).json()

    mcq = add("MCQ", 2, [{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}])
    multi = add(
        "MULTI_SELECT",
        3,
        [
            {"option_text": "A", "is_correct": True},
            {"option_text": "B", "is_correct": False},
            {"option_text": "C", "is_correct": True},
        ],
    )
    tf = add("TRUE_FALSE", 1, [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}])
    numerical = add("NUMERICAL", 2, [{"option_text": "42", "is_correct": True}])
    short = add("SHORT_ANSWER", 2, [])

    publish = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert publish.status_code == 200, publish.text

    return assessment, {"mcq": mcq, "multi": multi, "tf": tf, "numerical": numerical, "short": short}


def test_start_attempt_hides_correct_answers(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, questions = _build_full_assessment(client, token, batch["id"], subject["id"])

    response = client.post(f"/assessments/{assessment['id']}/attempts", headers=auth_headers(student["access_token"]))
    assert response.status_code == 201
    body = response.json()
    for q in body["questions"]:
        for opt in q["options"]:
            assert opt["is_correct"] is None


def test_full_attempt_flow_and_scoring(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"])
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    def option_id(question, text):
        return next(o["id"] for o in question["options"] if o["option_text"] == text)

    # Autosave each response individually, as the real UI would.
    r1 = client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": [option_id(q["mcq"], "4")]},
        headers=headers,
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/attempts/{attempt_id}/responses",
        json={
            "question_id": q["multi"]["id"],
            "selected_option_ids": [option_id(q["multi"], "A"), option_id(q["multi"], "C")],
        },
        headers=headers,
    )
    assert r2.status_code == 200

    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["tf"]["id"], "selected_option_ids": [option_id(q["tf"], "True")]},
        headers=headers,
    )
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["numerical"]["id"], "response_text": "42"},
        headers=headers,
    )
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["short"]["id"], "response_text": "Because of the quadratic formula."},
        headers=headers,
    )

    submit = client.post(f"/attempts/{attempt_id}/submit", headers=headers)
    assert submit.status_code == 200
    assert submit.json()["status"] == "SUBMITTED"
    # Short-answer is ungraded so far -> only the 2+3+1+2 objective marks count.
    assert submit.json()["total_score"] == 8

    review = client.get(f"/attempts/{attempt_id}/review", headers=headers).json()
    by_question = {r["question_id"]: r for r in review["responses"]}
    assert by_question[q["mcq"]["id"]]["is_correct"] is True
    assert by_question[q["mcq"]["id"]]["score"] == 2
    assert by_question[q["multi"]["id"]]["is_correct"] is True
    assert by_question[q["multi"]["id"]]["score"] == 3
    assert by_question[q["tf"]["id"]]["is_correct"] is True
    assert by_question[q["numerical"]["id"]]["is_correct"] is True
    assert by_question[q["short"]["id"]]["score"] is None

    # Teacher grades the subjective question.
    grade = client.patch(
        f"/assessments/{assessment['id']}/attempts/{attempt_id}/responses/{q['short']['id']}/grade",
        json={"score": 1.5},
        headers=auth_headers(token),
    )
    assert grade.status_code == 200

    final_attempt = client.get(f"/attempts/{attempt_id}", headers=headers).json()
    assert final_attempt["total_score"] == 9.5


def test_multi_select_partial_match_scores_zero(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"])
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    def option_id(question, text):
        return next(o["id"] for o in question["options"] if o["option_text"] == text)

    # Only one of the two correct options selected -> should NOT be credited (all-or-nothing).
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["multi"]["id"], "selected_option_ids": [option_id(q["multi"], "A")]},
        headers=headers,
    )
    client.post(f"/attempts/{attempt_id}/submit", headers=headers)

    review = client.get(f"/attempts/{attempt_id}/review", headers=headers).json()
    by_question = {r["question_id"]: r for r in review["responses"]}
    assert by_question[q["multi"]["id"]]["is_correct"] is False
    assert by_question[q["multi"]["id"]]["score"] == 0


def test_numerical_wrong_answer_and_unparseable_text(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"])
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    response = client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["numerical"]["id"], "response_text": "not-a-number"},
        headers=headers,
    )
    assert response.status_code == 200

    client.post(f"/attempts/{attempt_id}/submit", headers=headers)
    review = client.get(f"/attempts/{attempt_id}/review", headers=headers).json()
    by_question = {r["question_id"]: r for r in review["responses"]}
    assert by_question[q["numerical"]["id"]]["is_correct"] is False
    assert by_question[q["numerical"]["id"]]["score"] == 0


def test_resubmitting_a_response_overwrites_previous_answer(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"])
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    def option_id(question, text):
        return next(o["id"] for o in question["options"] if o["option_text"] == text)

    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": [option_id(q["mcq"], "3")]},
        headers=headers,
    )
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": [option_id(q["mcq"], "4")]},
        headers=headers,
    )
    client.post(f"/attempts/{attempt_id}/submit", headers=headers)

    review = client.get(f"/attempts/{attempt_id}/review", headers=headers).json()
    by_question = {r["question_id"]: r for r in review["responses"]}
    assert by_question[q["mcq"]["id"]]["is_correct"] is True
    assert len(by_question[q["mcq"]["id"]]["selected_option_ids"]) == 1


def test_cannot_attempt_unpublished_assessment(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment = client.post(
        "/assessments",
        json={"batch_id": batch["id"], "subject_id": subject["id"], "title": "Draft", "duration_minutes": 10, "total_marks": 1},
        headers=auth_headers(token),
    ).json()

    response = client.post(f"/assessments/{assessment['id']}/attempts", headers=auth_headers(student["access_token"]))
    assert response.status_code == 404


def test_cannot_attempt_if_not_enrolled(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    assessment, _q = _build_full_assessment(client, token, batch["id"], subject["id"])

    outsider = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.post(f"/assessments/{assessment['id']}/attempts", headers=auth_headers(outsider["access_token"]))
    assert response.status_code == 404


def test_starting_twice_resumes_same_attempt(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, _q = _build_full_assessment(client, token, batch["id"], subject["id"])
    headers = auth_headers(student["access_token"])

    first = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    second = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    assert first["id"] == second["id"]


def test_student_cannot_access_another_students_attempt(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student_a = _enroll_student(client, token, batch["id"], "rahul@test.com", "Rahul Sharma")
    student_b = _enroll_student(client, token, batch["id"], "ananya@test.com", "Ananya Gupta")
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"])

    start = client.post(
        f"/assessments/{assessment['id']}/attempts", headers=auth_headers(student_a["access_token"])
    ).json()

    get_response = client.get(f"/attempts/{start['id']}", headers=auth_headers(student_b["access_token"]))
    assert get_response.status_code == 404

    submit_response = client.post(
        f"/attempts/{start['id']}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": []},
        headers=auth_headers(student_b["access_token"]),
    )
    assert submit_response.status_code == 404


def test_expired_attempt_rejects_new_responses_and_autofinalizes(client, db_session):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"], duration_minutes=10)
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    # Backdate started_at so the attempt is already past its 10-minute window.
    attempt = db_session.get(AssessmentAttempt, uuid.UUID(attempt_id))
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    db_session.commit()

    response = client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": []},
        headers=headers,
    )
    assert response.status_code == 403

    status_check = client.get(f"/attempts/{attempt_id}", headers=headers).json()
    assert status_check["status"] == "EXPIRED"
    assert status_check["submitted_at"] is not None


def test_submit_after_expiry_is_a_safe_noop(client, db_session):
    token = _teacher_token(client)
    batch, subject = _setup_batch_subject(client, token)
    student = _enroll_student(client, token, batch["id"])
    assessment, q = _build_full_assessment(client, token, batch["id"], subject["id"], duration_minutes=10)
    headers = auth_headers(student["access_token"])

    start = client.post(f"/assessments/{assessment['id']}/attempts", headers=headers).json()
    attempt_id = start["id"]

    def option_id(question, text):
        return next(o["id"] for o in question["options"] if o["option_text"] == text)

    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q["mcq"]["id"], "selected_option_ids": [option_id(q["mcq"], "4")]},
        headers=headers,
    )

    attempt = db_session.get(AssessmentAttempt, uuid.UUID(attempt_id))
    attempt.started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    db_session.commit()

    submit = client.post(f"/attempts/{attempt_id}/submit", headers=headers)
    assert submit.status_code == 200
    assert submit.json()["status"] == "EXPIRED"
    assert submit.json()["total_score"] == 2
