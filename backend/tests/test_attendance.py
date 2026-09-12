from datetime import date, timedelta

from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _setup_batch_with_students(client, token, n=3):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    for i in range(n):
        client.post(
            f"/batches/{batch['id']}/students",
            json={"name": f"Student {i}", "email": f"student{i}@test.com"},
            headers=auth_headers(token),
        )
    students = client.get("/students", headers=auth_headers(token)).json()
    return batch, students


def test_mark_and_read_attendance(client):
    token = _teacher_token(client)
    batch, students = _setup_batch_with_students(client, token, n=2)
    today = date.today().isoformat()

    response = client.post(
        f"/batches/{batch['id']}/attendance",
        json={
            "date": today,
            "records": [
                {"student_id": students[0]["id"], "status": "PRESENT"},
                {"student_id": students[1]["id"], "status": "ABSENT"},
            ],
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 204

    roster = client.get(f"/batches/{batch['id']}/attendance?date={today}", headers=auth_headers(token)).json()
    statuses = {r["student_id"]: r["status"] for r in roster}
    assert statuses[students[0]["id"]] == "PRESENT"
    assert statuses[students[1]["id"]] == "ABSENT"


def test_marking_twice_on_same_day_overwrites(client):
    token = _teacher_token(client)
    batch, students = _setup_batch_with_students(client, token, n=1)
    today = date.today().isoformat()

    client.post(
        f"/batches/{batch['id']}/attendance",
        json={"date": today, "records": [{"student_id": students[0]["id"], "status": "ABSENT"}]},
        headers=auth_headers(token),
    )
    client.post(
        f"/batches/{batch['id']}/attendance",
        json={"date": today, "records": [{"student_id": students[0]["id"], "status": "PRESENT"}]},
        headers=auth_headers(token),
    )

    roster = client.get(f"/batches/{batch['id']}/attendance?date={today}", headers=auth_headers(token)).json()
    assert len(roster) == 1
    assert roster[0]["status"] == "PRESENT"


def test_attendance_percentage_counts_late_as_present(client):
    token = _teacher_token(client)
    batch, students = _setup_batch_with_students(client, token, n=1)
    student_id = students[0]["id"]
    today = date.today()

    for i, status in enumerate(["PRESENT", "LATE", "ABSENT", "PRESENT"]):
        day = (today - timedelta(days=i)).isoformat()
        client.post(
            f"/batches/{batch['id']}/attendance",
            json={"date": day, "records": [{"student_id": student_id, "status": status}]},
            headers=auth_headers(token),
        )

    result = client.get(f"/students/{student_id}/attendance", headers=auth_headers(token)).json()
    assert result["total_days"] == 4
    assert result["present_days"] == 3  # PRESENT + LATE + PRESENT
    assert result["attendance_percentage"] == 75.0


def test_cannot_mark_attendance_for_student_not_in_batch(client):
    token = _teacher_token(client)
    batch, _students = _setup_batch_with_students(client, token, n=0)
    outsider = register(client, "Outsider", "outsider@test.com")

    response = client.post(
        f"/batches/{batch['id']}/attendance",
        json={"date": date.today().isoformat(), "records": [{"student_id": outsider["user"]["id"], "status": "PRESENT"}]},
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_teacher_cannot_mark_attendance_for_another_teachers_batch(client):
    token_a = _teacher_token(client, "a@test.com")
    token_b = _teacher_token(client, "b@test.com")
    batch, students = _setup_batch_with_students(client, token_a, n=1)

    response = client.post(
        f"/batches/{batch['id']}/attendance",
        json={"date": date.today().isoformat(), "records": [{"student_id": students[0]["id"], "status": "PRESENT"}]},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404


def test_student_can_view_own_attendance_but_not_anothers(client):
    token = _teacher_token(client)
    batch, students = _setup_batch_with_students(client, token, n=0)

    self_student = register(client, "Self", "self@test.com")
    client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Self", "email": "self@test.com"},
        headers=auth_headers(token),
    )
    other_student = register(client, "Other", "other@test.com")

    own = client.get(
        f"/students/{self_student['user']['id']}/attendance", headers=auth_headers(self_student["access_token"])
    )
    assert own.status_code == 200

    forbidden = client.get(
        f"/students/{self_student['user']['id']}/attendance", headers=auth_headers(other_student["access_token"])
    )
    assert forbidden.status_code == 404
