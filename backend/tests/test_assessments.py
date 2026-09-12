from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup(client, token):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    return batch, subject


def _create_assessment(client, token, batch_id, subject_id, total_marks=10, duration_minutes=30):
    return client.post(
        "/assessments",
        json={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "title": "Unit Test",
            "duration_minutes": duration_minutes,
            "total_marks": total_marks,
        },
        headers=auth_headers(token),
    ).json()


def _add_question(client, token, assessment_id, **kwargs):
    payload = {
        "question_text": kwargs.pop("question_text", "Q"),
        "question_type": kwargs.pop("question_type"),
        "marks": kwargs.pop("marks", 1),
        "options": kwargs.pop("options", []),
    }
    payload.update(kwargs)
    return client.post(f"/assessments/{assessment_id}/questions", json=payload, headers=auth_headers(token))


def test_create_assessment_is_draft(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"])
    assert assessment["status"] == "DRAFT"


def test_create_assessment_requires_own_batch(client):
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch, subject = _setup(client, token_a)

    response = client.post(
        "/assessments",
        json={
            "batch_id": batch["id"],
            "subject_id": subject["id"],
            "title": "Hijack",
            "duration_minutes": 30,
            "total_marks": 10,
        },
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404


def test_add_mcq_question(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"])

    response = _add_question(
        client,
        token,
        assessment["id"],
        question_type="MCQ",
        marks=2,
        options=[
            {"option_text": "3", "is_correct": False},
            {"option_text": "4", "is_correct": True},
        ],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["options"]) == 2
    assert body["options"][1]["is_correct"] is True


def test_publish_fails_with_no_questions(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=10)

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 422
    assert "at least one question" in response.json()["error"]["message"]["errors"][0]


def test_publish_fails_with_empty_correct_answer_set(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client,
        token,
        assessment["id"],
        question_type="MCQ",
        marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": False}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 422
    errors = response.json()["error"]["message"]["errors"]
    assert any("exactly one correct option" in e for e in errors)


def test_publish_fails_with_marks_mismatch(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=99)
    _add_question(
        client,
        token,
        assessment["id"],
        question_type="MCQ",
        marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 422
    errors = response.json()["error"]["message"]["errors"]
    assert any("does not match" in e for e in errors)


def test_publish_fails_with_orphaned_options_on_subjective(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client,
        token,
        assessment["id"],
        question_type="SHORT_ANSWER",
        marks=2,
        options=[{"option_text": "should not be here", "is_correct": True}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 422
    errors = response.json()["error"]["message"]["errors"]
    assert any("must not have options" in e for e in errors)


def test_publish_fails_with_invalid_numerical_answer(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client,
        token,
        assessment["id"],
        question_type="NUMERICAL",
        marks=2,
        options=[{"option_text": "not-a-number", "is_correct": True}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 422
    errors = response.json()["error"]["message"]["errors"]
    assert any("valid number" in e for e in errors)


def test_publish_succeeds_with_valid_assessment(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=4)
    _add_question(
        client, token, assessment["id"], question_type="MCQ", marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
    )
    _add_question(
        client, token, assessment["id"], question_type="TRUE_FALSE", marks=2,
        options=[{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PUBLISHED"


def test_cannot_add_question_after_publish(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client, token, assessment["id"], question_type="MCQ", marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
    )
    client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))

    response = _add_question(client, token, assessment["id"], question_type="MCQ", marks=1, options=[])
    assert response.status_code == 409


def test_only_owner_can_publish(client):
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch, subject = _setup(client, token_a)
    assessment = _create_assessment(client, token_a, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client, token_a, assessment["id"], question_type="MCQ", marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
    )

    response = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token_b))
    assert response.status_code == 404


def test_student_cannot_see_draft_or_review_assessment(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)

    student = register(client, "Rahul Sharma", "rahul@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Rahul Sharma", "email": "rahul@test.com"},
        headers=auth_headers(token),
    )

    listing = client.get("/assessments", headers=auth_headers(student["access_token"]))
    assert listing.json() == []

    detail = client.get(f"/assessments/{assessment['id']}", headers=auth_headers(student["access_token"]))
    assert detail.status_code == 404


def test_close_then_republish_rejected(client):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    assessment = _create_assessment(client, token, batch["id"], subject["id"], total_marks=2)
    _add_question(
        client, token, assessment["id"], question_type="MCQ", marks=2,
        options=[{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
    )
    client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    close_response = client.post(f"/assessments/{assessment['id']}/close", headers=auth_headers(token))
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"

    republish = client.post(f"/assessments/{assessment['id']}/publish", headers=auth_headers(token))
    assert republish.status_code == 409
