from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def _create_batch_with_student(client, teacher_token, student_email):
    batch = client.post(
        "/batches", json={"name": "Class 10-A"}, headers=auth_headers(teacher_token)
    ).json()
    added = client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Rahul Sharma", "email": student_email},
        headers=auth_headers(teacher_token),
    ).json()
    return batch, added["student_id"]


def test_teacher_dashboard_counts(client):
    token = _teacher_token(client)
    _create_batch_with_student(client, token, "rahul@test.com")

    response = client.get("/teachers/dashboard", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json() == {"total_batches": 1, "total_students": 1}


def test_teacher_can_view_own_student(client):
    token = _teacher_token(client)
    _batch, student_id = _create_batch_with_student(client, token, "rahul@test.com")

    response = client.get(f"/students/{student_id}", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["email"] == "rahul@test.com"


def test_teacher_cannot_view_unrelated_student(client):
    token_a = _teacher_token(client, "teacherA@test.com")
    token_b = _teacher_token(client, "teacherB@test.com")
    _batch, student_id = _create_batch_with_student(client, token_a, "rahul@test.com")

    response = client.get(f"/students/{student_id}", headers=auth_headers(token_b))
    assert response.status_code == 404


def test_student_cannot_view_another_students_record(client):
    token = _teacher_token(client)
    _batch, student_a_id = _create_batch_with_student(client, token, "rahul@test.com")

    student_b = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.get(
        f"/students/{student_a_id}", headers=auth_headers(student_b["access_token"])
    )
    assert response.status_code == 404


def test_student_can_view_self_via_students_endpoint(client):
    student = register(client, "Ananya Gupta", "ananya@test.com")
    response = client.get(
        f"/students/{student['user']['id']}", headers=auth_headers(student["access_token"])
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ananya@test.com"
