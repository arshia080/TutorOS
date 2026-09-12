"""End-to-end test of the product spec's section 34 demo flow, exercised as
one continuous story rather than isolated unit tests (those already exist
per-feature in the other test files -- this one proves the features actually
compose):

teacher creates a batch, adds students, creates topics
  -> uploads a PDF -> AI extracts questions (mocked) -> teacher reviews & publishes
  -> a student attempts the test -> objective questions auto-graded
  -> performance updates (topic mastery becomes computable)
  -> teacher's Attention Panel surfaces the student's weak topic
  -> teacher/student generates a personalized practice set (mocked AI)
  -> student completes the practice set
  -> analytics (mastery before/after) update, with the causation disclaimer attached
"""

from fpdf import FPDF

from tests.conftest import auth_headers, register


def _sample_pdf_bytes() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        10,
        "1. What is the value of x in 2x = 10?\nA) 5  B) 10\n\n"
        "2. Is 7 a prime number?\nA) True  B) False\n\n"
        "Answer Key: 1-A, 2-A",
    )
    return bytes(pdf.output())


def test_full_section_34_demo_flow(client, fake_ai_provider):
    # --- Teacher sets up the class ---
    teacher = register(client, "Priya Nair", "priya@test.com", role="TEACHER")
    teacher_token = teacher["access_token"]
    headers_t = auth_headers(teacher_token)

    batch = client.post("/batches", json={"name": "Class 10-A Mathematics"}, headers=headers_t).json()
    subject = client.post("/subjects", json={"name": "Mathematics", "grade": "10"}, headers=headers_t).json()
    algebra = client.post("/topics", json={"subject_id": subject["id"], "name": "Algebra"}, headers=headers_t).json()
    client.post("/topics", json={"subject_id": subject["id"], "name": "Number Theory"}, headers=headers_t)

    student = register(client, "Rahul Sharma", "rahul@test.com")
    student_id = student["user"]["id"]
    client.post(
        f"/batches/{batch['id']}/students", json={"name": "Rahul Sharma", "email": "rahul@test.com"}, headers=headers_t
    )

    # --- Teacher uploads a PDF; AI extraction is mocked but the real PDF-text
    # extraction (pypdf) and the real validation gate both run for real. ---
    fake_ai_provider.structured_response = {
        "questions": [
            {
                "question_text": "What is the value of x in 2x = 10?",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 5,
                "topic_name": "Algebra",
                "options": [{"option_text": "5", "is_correct": True}, {"option_text": "10", "is_correct": False}],
            },
            {
                "question_text": "Is 7 a prime number?",
                "question_type": "TRUE_FALSE",
                "difficulty": "EASY",
                "marks": 5,
                "topic_name": "Algebra",
                "options": [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
            },
        ]
    }
    extract_response = client.post(
        "/ai/pdf-extract",
        data={"batch_id": batch["id"], "subject_id": subject["id"]},
        files={"file": ("Class10_Maths_Test.pdf", _sample_pdf_bytes(), "application/pdf")},
        headers=headers_t,
    )
    assert extract_response.status_code == 202
    job_id = extract_response.json()["id"]

    # TestClient runs BackgroundTasks synchronously -- the job is already done.
    job = client.get(f"/ai/jobs/{job_id}", headers=headers_t).json()
    assert job["status"] == "COMPLETED"
    assessment_id = job["assessment_id"]

    assessment = client.get(f"/assessments/{assessment_id}", headers=headers_t).json()
    assert assessment["status"] == "DRAFT"  # never auto-published

    questions = client.get(f"/assessments/{assessment_id}/questions", headers=headers_t).json()
    assert len(questions) == 2
    assert all(q["source"] == "AI_EXTRACTED" for q in questions)
    assert all(q["topic_id"] == algebra["id"] for q in questions)  # topic_name resolved correctly

    # --- Teacher reviews (no edits needed here) and explicitly publishes ---
    publish = client.post(f"/assessments/{assessment_id}/publish", headers=headers_t)
    assert publish.status_code == 200, publish.text
    assert publish.json()["status"] == "PUBLISHED"

    # --- Student attempts the test: gets question 1 right, question 2 wrong ---
    headers_s = auth_headers(student["access_token"])
    start = client.post(f"/assessments/{assessment_id}/attempts", headers=headers_s).json()
    attempt_id = start["id"]
    q_by_text = {q["question_text"]: q for q in start["questions"]}

    q1 = q_by_text["What is the value of x in 2x = 10?"]
    correct_opt = next(o["id"] for o in q1["options"] if o["option_text"] == "5")
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q1["id"], "selected_option_ids": [correct_opt]},
        headers=headers_s,
    )
    q2 = q_by_text["Is 7 a prime number?"]
    wrong_opt = next(o["id"] for o in q2["options"] if o["option_text"] == "False")
    client.post(
        f"/attempts/{attempt_id}/responses",
        json={"question_id": q2["id"], "selected_option_ids": [wrong_opt]},
        headers=headers_s,
    )
    submit = client.post(f"/attempts/{attempt_id}/submit", headers=headers_s)
    assert submit.status_code == 200
    assert submit.json()["total_score"] == 5  # only question 1 correct

    # --- Performance updates: the topic now has computable mastery ---
    perf = client.get(f"/students/{student_id}/performance", headers=headers_t).json()
    algebra_perf = next(t for t in perf["topics"] if t["topic_id"] == algebra["id"])
    assert algebra_perf["accuracy"] == 50.0  # 5/10 marks correct

    # --- Teacher's Attention Panel surfaces this student's weak topic ---
    panel = client.get(f"/batches/{batch['id']}/attention-panel", headers=headers_t).json()
    assert len(panel) == 1
    assert panel[0]["student_id"] == student_id
    assert panel[0]["topic_id"] == algebra["id"]
    mastery_before_practice = panel[0]["mastery_score"]

    # --- Generate a personalized practice set targeting the weak topic ---
    fake_ai_provider.structured_response = {
        "questions": [
            {
                "question_text": f"Practice easy Q{i}", "question_type": "MCQ", "difficulty": "EASY", "marks": 1,
                "options": [{"option_text": "A", "is_correct": True}, {"option_text": "B", "is_correct": False}],
            }
            for i in range(2)
        ]
        + [
            {
                "question_text": "Practice medium Q1", "question_type": "TRUE_FALSE", "difficulty": "MEDIUM", "marks": 1,
                "options": [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
            }
        ]
    }
    practice = client.post(
        f"/students/{student_id}/topics/{algebra['id']}/practice",
        json={"easy_count": 2, "medium_count": 1, "hard_count": 0},
        headers=headers_s,
    )
    assert practice.status_code == 201, practice.text
    practice_set = practice.json()
    assert practice_set["mastery_before"] == mastery_before_practice

    # --- Student completes the practice set, answering everything correctly ---
    for q in practice_set["questions"]:
        correct = q["options"][0]["id"]  # first option is always correct by construction above
        r = client.post(
            f"/practice-sets/{practice_set['id']}/responses",
            json={"question_id": q["id"], "selected_option_id": correct},
            headers=headers_s,
        )
        assert r.status_code == 200

    completion = client.post(f"/practice-sets/{practice_set['id']}/complete", headers=headers_s)
    assert completion.status_code == 200, completion.text
    result = completion.json()

    # --- Analytics update: mastery moved, and the causation disclaimer is attached ---
    assert result["mastery_before"] == mastery_before_practice
    assert result["mastery_after"] > result["mastery_before"]  # all-correct practice should improve it
    assert "observed change" in result["note"]
    assert all(r["is_correct"] for r in result["responses"])
