from tests.conftest import auth_headers, register


def _teacher_token(client, email="teacher@test.com"):
    return register(client, "Priya Nair", email, role="TEACHER")["access_token"]


def test_create_and_list_batches(client):
    token = _teacher_token(client)
    response = client.post(
        "/batches", json={"name": "Class 10-A", "grade": "10", "section": "A"}, headers=auth_headers(token)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Class 10-A"
    assert body["student_count"] == 0

    response = client.get("/batches", headers=auth_headers(token))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_student_cannot_create_batch(client):
    student_token = register(client, "Rahul Sharma", "rahul@test.com")["access_token"]
    response = client.post(
        "/batches", json={"name": "Class 10-A"}, headers=auth_headers(student_token)
    )
    assert response.status_code == 403


def test_teacher_cannot_access_another_teachers_batch(client):
    token_a = _teacher_token(client, "teacherA@test.com")
    token_b = _teacher_token(client, "teacherB@test.com")

    batch = client.post(
        "/batches", json={"name": "Class 10-A"}, headers=auth_headers(token_a)
    ).json()

    get_response = client.get(f"/batches/{batch['id']}", headers=auth_headers(token_b))
    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/batches/{batch['id']}", json={"name": "Hijacked"}, headers=auth_headers(token_b)
    )
    assert patch_response.status_code == 404

    students_response = client.get(f"/batches/{batch['id']}/students", headers=auth_headers(token_b))
    assert students_response.status_code == 404


def test_add_new_student_to_batch(client):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()

    response = client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Ananya Gupta", "email": "ananya@test.com"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    assert response.json()["email"] == "ananya@test.com"

    roster = client.get(f"/batches/{batch['id']}/students", headers=auth_headers(token)).json()
    assert len(roster) == 1

    batch_detail = client.get(f"/batches/{batch['id']}", headers=auth_headers(token)).json()
    assert batch_detail["student_count"] == 1


def test_add_existing_student_to_batch(client):
    token = _teacher_token(client)
    student = register(client, "Aryan Verma", "aryan@test.com")
    batch = client.post("/batches", json={"name": "Class 10-B"}, headers=auth_headers(token)).json()

    response = client.post(
        f"/batches/{batch['id']}/students",
        json={"name": "Aryan Verma", "email": "aryan@test.com"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    assert response.json()["student_id"] == student["user"]["id"]


def test_cannot_add_same_student_twice(client):
    token = _teacher_token(client)
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(token)).json()
    payload = {"name": "Ananya Gupta", "email": "ananya@test.com"}
    client.post(f"/batches/{batch['id']}/students", json=payload, headers=auth_headers(token))
    response = client.post(f"/batches/{batch['id']}/students", json=payload, headers=auth_headers(token))
    assert response.status_code == 409


def test_add_student_to_nonexistent_batch_is_not_found(client):
    token = _teacher_token(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/batches/{fake_id}/students",
        json={"name": "Ananya Gupta", "email": "ananya@test.com"},
        headers=auth_headers(token),
    )
    assert response.status_code == 404
