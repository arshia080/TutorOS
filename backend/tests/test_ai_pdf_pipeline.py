import io

from fpdf import FPDF

from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup(client, token):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    return batch, subject


def _sample_pdf_bytes() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "1. What is 2 + 2?\nA) 3  B) 4\n\nAnswer Key: 1-B")
    return bytes(pdf.output())


def _valid_extraction():
    return {
        "questions": [
            {
                "question_text": "What is 2 + 2?",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 2,
                "topic_name": "Algebra",
                "options": [{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": True}],
            }
        ]
    }


def test_pdf_extraction_end_to_end(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    client.post("/topics", json={"subject_id": subject["id"], "name": "Algebra"}, headers=auth_headers(token))
    fake_ai_provider.structured_response = _valid_extraction()

    response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("test.pdf", _sample_pdf_bytes(), "application/pdf")},
        headers=auth_headers(token),
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] in ("PENDING", "PROCESSING", "COMPLETED")

    # TestClient runs BackgroundTasks synchronously, so it's already done by now.
    job_status = client.get(f"/ai/jobs/{job['id']}", headers=auth_headers(token)).json()
    assert job_status["status"] == "COMPLETED", job_status
    assert job_status["assessment_id"] is not None

    assessment = client.get(f"/assessments/{job_status['assessment_id']}", headers=auth_headers(token)).json()
    assert assessment["status"] == "DRAFT"

    questions = client.get(f"/assessments/{assessment['id']}/questions", headers=auth_headers(token)).json()
    assert len(questions) == 1
    assert questions[0]["source"] == "AI_EXTRACTED"
    assert questions[0]["question_text"] == "What is 2 + 2?"
    # Topic name was resolved to the real topic the teacher had already created.
    assert questions[0]["topic_id"] is not None


def test_pdf_extraction_job_fails_cleanly_on_malformed_ai_output(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.structured_response = {"questions": [{"question_type": "MCQ", "marks": 2, "options": []}]}

    response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("test.pdf", _sample_pdf_bytes(), "application/pdf")},
        headers=auth_headers(token),
    )
    job_id = response.json()["id"]

    job_status = client.get(f"/ai/jobs/{job_id}", headers=auth_headers(token)).json()
    assert job_status["status"] == "FAILED"
    assert job_status["assessment_id"] is None
    assert job_status["error_message"]

    assessments = client.get("/assessments", headers=auth_headers(token)).json()
    assert assessments == []


def test_non_pdf_file_rejected(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)

    response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
        headers=auth_headers(token),
    )
    assert response.status_code == 415


def test_cannot_extract_for_another_teachers_batch(client, fake_ai_provider):
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch, subject = _setup(client, token_a)

    response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("test.pdf", _sample_pdf_bytes(), "application/pdf")},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404


def test_provider_failure_marks_job_failed(client, fake_ai_provider):
    token = _teacher_token(client)
    batch, subject = _setup(client, token)
    fake_ai_provider.should_error = True

    response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("test.pdf", _sample_pdf_bytes(), "application/pdf")},
        headers=auth_headers(token),
    )
    job_id = response.json()["id"]
    job_status = client.get(f"/ai/jobs/{job_id}", headers=auth_headers(token)).json()
    assert job_status["status"] == "FAILED"
