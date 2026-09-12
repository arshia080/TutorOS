from tests.conftest import auth_headers, register


def _teacher_token(client):
    return register(client, "Priya Nair", "teacher@test.com", role="TEACHER")["access_token"]


def test_create_subject_and_topic(client):
    token = _teacher_token(client)
    subject = client.post(
        "/subjects", json={"name": "Mathematics", "grade": "10"}, headers=auth_headers(token)
    ).json()

    topic = client.post(
        "/topics",
        json={"subject_id": subject["id"], "name": "Trigonometry", "chapter": "Chapter 4"},
        headers=auth_headers(token),
    )
    assert topic.status_code == 201
    assert topic.json()["subject_id"] == subject["id"]

    topics = client.get(f"/topics?subject_id={subject['id']}", headers=auth_headers(token))
    assert topics.status_code == 200
    assert len(topics.json()) == 1


def test_topic_requires_existing_subject(client):
    token = _teacher_token(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/topics",
        json={"subject_id": fake_id, "name": "Trigonometry"},
        headers=auth_headers(token),
    )
    assert response.status_code == 404


def test_student_cannot_manage_subjects(client):
    student_token = register(client, "Rahul Sharma", "rahul@test.com")["access_token"]
    response = client.post(
        "/subjects", json={"name": "Mathematics"}, headers=auth_headers(student_token)
    )
    assert response.status_code == 403
