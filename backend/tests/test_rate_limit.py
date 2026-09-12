from app.core.config import settings
from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _valid_generated_set():
    return {
        "questions": [
            {
                "question_text": "What is 2+2?",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 2,
                "options": [{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
            }
        ]
    }


def test_ai_generation_rate_limited_after_threshold(client, fake_ai_provider, monkeypatch):
    monkeypatch.setattr(settings, "ai_rate_limit_per_minute", 3)
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    fake_ai_provider.structured_response = _valid_generated_set()

    payload = {
        "batch_id": batch["id"],
        "subject_id": subject["id"],
        "grade": "10",
        "count": 1,
        "difficulty": "EASY",
        "question_types": ["MCQ"],
        "total_marks": 2,
        "duration_minutes": 10,
    }

    statuses = [client.post("/ai/generate-questions", json=payload, headers=auth_headers(token)).status_code for _ in range(4)]
    assert statuses[:3] == [201, 201, 201]
    assert statuses[3] == 429


def test_rate_limit_is_per_user(client, fake_ai_provider, monkeypatch):
    monkeypatch.setattr(settings, "ai_rate_limit_per_minute", 1)
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch_a = client.post("/batches", json={"name": "A"}, headers=auth_headers(token_a)).json()
    subject_a = client.post("/subjects", json={"name": "Math"}, headers=auth_headers(token_a)).json()
    batch_b = client.post("/batches", json={"name": "B"}, headers=auth_headers(token_b)).json()
    subject_b = client.post("/subjects", json={"name": "Math"}, headers=auth_headers(token_b)).json()
    fake_ai_provider.structured_response = _valid_generated_set()

    def payload(batch, subject):
        return {
            "batch_id": batch["id"], "subject_id": subject["id"], "grade": "10", "count": 1,
            "difficulty": "EASY", "question_types": ["MCQ"], "total_marks": 2, "duration_minutes": 10,
        }

    first = client.post("/ai/generate-questions", json=payload(batch_a, subject_a), headers=auth_headers(token_a))
    second_same_user = client.post("/ai/generate-questions", json=payload(batch_a, subject_a), headers=auth_headers(token_a))
    other_user = client.post("/ai/generate-questions", json=payload(batch_b, subject_b), headers=auth_headers(token_b))

    assert first.status_code == 201
    assert second_same_user.status_code == 429
    assert other_user.status_code == 201  # a different user's own limit, unaffected
