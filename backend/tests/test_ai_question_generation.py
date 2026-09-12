from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup(client, token):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    return batch, subject


def _valid_generated_set():
    return {
        "questions": [
            {
                "question_text": "What is 2+2?",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 2,
                "options": [{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
            },
            {
                "question_text": "The sky is blue.",
                "question_type": "TRUE_FALSE",
                "difficulty": "EASY",
                "marks": 1,
                "options": [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
            },
        ]
    }


def _request_payload(batch, subject, **overrides):
    payload = {
        "batch_id": batch["id"],
        "subject_id": subject["id"],
        "grade": "10",
        "count": 2,
        "difficulty": "EASY",
        "question_types": ["MCQ", "TRUE_FALSE"],
        "total_marks": 3,
        "duration_minutes": 15,
    }
    payload.update(overrides)
    return payload


def test_successful_generation_creates_draft_assessment(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.structured_response = _valid_generated_set()

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 201, response.text
    assessment = response.json()
    assert assessment["status"] == "DRAFT"

    questions = client.get(f"/assessments/{assessment['id']}/questions", headers=auth_headers(token)).json()
    assert len(questions) == 2
    assert all(q["source"] == "AI_GENERATED" for q in questions)


def test_never_auto_published(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.structured_response = _valid_generated_set()

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assessment_id = response.json()["id"]

    detail = client.get(f"/assessments/{assessment_id}", headers=auth_headers(token)).json()
    assert detail["status"] == "DRAFT"


def test_missing_field_rejected_and_nothing_persisted(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.structured_response = {
        "questions": [{"question_type": "MCQ", "difficulty": "EASY", "marks": 2, "options": []}]
    }

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 422

    assessments = client.get("/assessments", headers=auth_headers(token)).json()
    assert assessments == []


def test_duplicate_questions_rejected(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    data = _valid_generated_set()
    data["questions"][1] = dict(data["questions"][0])  # exact duplicate
    fake_ai_provider.structured_response = data

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 422
    assert any("Duplicate" in e for e in response.json()["error"]["message"]["errors"])


def test_missing_correct_answer_rejected(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    data = _valid_generated_set()
    for opt in data["questions"][0]["options"]:
        opt["is_correct"] = False
    fake_ai_provider.structured_response = data

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 422


def test_invalid_question_type_rejected(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    data = _valid_generated_set()
    data["questions"][0]["question_type"] = "ESSAY"
    fake_ai_provider.structured_response = data

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 422


def test_teacher_cannot_generate_for_another_teachers_batch(client, fake_ai_provider):
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch, subject = _setup(client, token_a)
    fake_ai_provider.structured_response = _valid_generated_set()

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token_b))
    assert response.status_code == 404


def test_provider_failure_returns_502(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.should_error = True

    response = client.post("/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token))
    assert response.status_code == 502


def test_regenerate_question(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.structured_response = _valid_generated_set()
    assessment = client.post(
        "/ai/generate-questions", json=_request_payload(batch, subject), headers=auth_headers(token)
    ).json()
    questions = client.get(f"/assessments/{assessment['id']}/questions", headers=auth_headers(token)).json()
    original_text = questions[0]["question_text"]

    fake_ai_provider.structured_response = {
        "questions": [
            {
                "question_text": "What is 3+3?",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 2,
                "options": [{"option_text": "5", "is_correct": False}, {"option_text": "6", "is_correct": True}],
            }
        ]
    }
    response = client.post(
        f"/ai/assessments/{assessment['id']}/questions/{questions[0]['id']}/regenerate", headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    assert response.json()["question_text"] != original_text
    assert response.json()["question_text"] == "What is 3+3?"


def test_student_cannot_generate_questions(client, fake_ai_provider):
    student = register(client, "Rahul Sharma", "rahul@test.com")
    fake_ai_provider.structured_response = _valid_generated_set()
    response = client.post(
        "/ai/generate-questions",
        json={
            "batch_id": "00000000-0000-0000-0000-000000000000",
            "subject_id": "00000000-0000-0000-0000-000000000000",
            "grade": "10",
            "count": 1,
            "difficulty": "EASY",
            "question_types": ["MCQ"],
            "total_marks": 2,
            "duration_minutes": 10,
        },
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 403
