from datetime import datetime, timedelta, timezone

from tests.conftest import auth_headers, register

PDF_BYTES = b"%PDF-1.4 fake content for tests"


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup_batch_with_subject(client, token):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(token)).json()
    return batch, subject


def _add_student(client, token, batch_id, email="rahul@test.com", name="Rahul Sharma"):
    response = client.post(
        f"/batches/{batch_id}/students", json={"name": name, "email": email}, headers=auth_headers(token)
    )
    return response.json()["student_id"]


def _create_homework(client, token, batch_id, subject_id, due_date, with_file=True):
    files = [("files", ("worksheet.pdf", PDF_BYTES, "application/pdf"))] if with_file else []
    return client.post(
        "/homework",
        data={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "title": "Chapter 4 worksheet",
            "description": "Complete all questions",
            "due_date": due_date.isoformat(),
        },
        files=files or None,
        headers=auth_headers(token),
    )


def test_create_homework_with_attachment(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)

    response = _create_homework(client, token, batch["id"], subject["id"], due_date)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Chapter 4 worksheet"
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["mime_type"] == "application/pdf"


def test_create_homework_rejects_unsupported_file_type(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)

    response = client.post(
        "/homework",
        data={
            "batch_id": batch["id"],
            "subject_id": subject["id"],
            "title": "Bad file",
            "due_date": due_date.isoformat(),
        },
        files=[("files", ("script.exe", b"MZ", "application/x-msdownload"))],
        headers=auth_headers(token),
    )
    assert response.status_code == 415


def test_create_homework_requires_own_batch(client):
    token_a = _teacher_token(client, "teacherA@test.com")
    token_b = _teacher_token(client, "teacherB@test.com")
    batch_a, subject_a = _setup_batch_with_subject(client, token_a)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)

    response = _create_homework(client, token_b, batch_a["id"], subject_a["id"], due_date)
    assert response.status_code == 404


def test_download_attachment_scoped(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    student_id = _add_student(client, token, batch["id"])
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date).json()
    attachment_id = homework["attachments"][0]["id"]

    teacher_download = client.get(
        f"/homework/{homework['id']}/attachments/{attachment_id}/file", headers=auth_headers(token)
    )
    assert teacher_download.status_code == 200
    assert teacher_download.content == PDF_BYTES

    outsider = register(client, "Ananya Gupta", "ananya@test.com")
    outsider_download = client.get(
        f"/homework/{homework['id']}/attachments/{attachment_id}/file",
        headers=auth_headers(outsider["access_token"]),
    )
    assert outsider_download.status_code == 404


def test_student_sees_only_own_batch_homework(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    _create_homework(client, token, batch["id"], subject["id"], due_date)

    # Self-registered students so we control their password and can authenticate as them.
    in_batch = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    outside_batch = register(client, "Kabir Malhotra", "kabir@test.com")

    listing = client.get("/homework", headers=auth_headers(in_batch["access_token"]))
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    other_listing = client.get("/homework", headers=auth_headers(outside_batch["access_token"]))
    assert other_listing.status_code == 200
    assert len(other_listing.json()) == 0


def test_submit_before_deadline(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    response = client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "SUBMITTED"


def test_submit_after_deadline_rejected(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    due_date = datetime.now(timezone.utc) - timedelta(days=1)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    response = client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 403


def test_submit_after_deadline_allowed_when_reopened(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    due_date = datetime.now(timezone.utc) - timedelta(days=1)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()
    client.patch(
        f"/homework/{homework['id']}", json={"allow_late_submissions": True}, headers=auth_headers(token)
    )

    response = client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student["access_token"]),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "LATE"


def test_resubmission_replaces_previous(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("first.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student["access_token"]),
    )
    second = client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("second.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student["access_token"]),
    )
    assert second.status_code == 201
    assert second.json()["file_name"] == "second.pdf"

    roster = client.get(f"/homework/{homework['id']}/submissions", headers=auth_headers(token)).json()
    assert len(roster) == 1


def test_student_not_in_batch_cannot_submit(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    outsider = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(outsider["access_token"]),
    )
    assert response.status_code == 404


def test_student_cannot_view_another_students_submission(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    student_a = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(student_a["access_token"]),
    )

    student_b = register(client, "Kabir Malhotra", "kabir@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Kabir Malhotra", "email": "kabir@test.com"},
        headers=auth_headers(token),
    )

    student_a_id = client.get(
        f"/homework/{homework['id']}/submissions/me", headers=auth_headers(student_a["access_token"])
    ).json()["student_id"]

    response = client.get(
        f"/homework/{homework['id']}/submissions/{student_a_id}",
        headers=auth_headers(student_b["access_token"]),
    )
    assert response.status_code == 404

    teacher_view = client.get(
        f"/homework/{homework['id']}/submissions/{student_a_id}", headers=auth_headers(token)
    )
    assert teacher_view.status_code == 200


def test_roster_shows_pending_and_submitted(client):
    token = _teacher_token(client)
    batch, subject = _setup_batch_with_subject(client, token)
    due_date = datetime.now(timezone.utc) + timedelta(days=3)
    homework = _create_homework(client, token, batch["id"], subject["id"], due_date, with_file=False).json()

    submitted_student = register(client, "Ishita Singh", "ishita@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ishita Singh", "email": "ishita@test.com"},
        headers=auth_headers(token),
    )
    client.post(
        f"/homework/{homework['id']}/submissions",
        files={"file": ("answers.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(submitted_student["access_token"]),
    )

    _add_student(client, token, batch["id"], "pending@test.com", "Pending Student")

    roster = client.get(f"/homework/{homework['id']}/submissions", headers=auth_headers(token)).json()
    statuses = {entry["email"]: entry["status"] for entry in roster}
    assert statuses["ishita@test.com"] == "SUBMITTED"
    assert statuses["pending@test.com"] is None
