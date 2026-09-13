"""Phase 8: Parent Portal.

The authorization tests here are the highest-priority tests in this file --
a bug here leaks a child's academic data to the wrong adult. Every "should
fail" case is written explicitly (expecting 403/404), not just asserted as a
side effect of a happy-path test.
"""

import uuid

from tests.conftest import auth_headers, register


def _teacher(client, email="teacher-p8@test.com"):
    reg = register(client, "Priya Nair", email, role="TEACHER")
    return reg["access_token"], reg["user"]["id"]


def _parent(client, email="parent-p8@test.com"):
    reg = register(client, "Sunita Sharma", email, role="PARENT")
    return reg["access_token"], reg["user"]["id"]


def _batch_with_student(client, teacher_token, student_email="child-p8@test.com", student_name="Rahul Sharma"):
    batch = client.post("/batches", json={"name": "Class 10-A"}, headers=auth_headers(teacher_token)).json()
    student_resp = client.post(
        f"/batches/{batch['id']}/students",
        json={"name": student_name, "email": student_email},
        headers=auth_headers(teacher_token),
    ).json()
    return batch["id"], student_resp["student_id"]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_parent_can_register_and_login(client):
    reg = register(client, "Sunita Sharma", "sunita@test.com", role="PARENT")
    assert reg["user"]["role"] == "PARENT"

    login = client.post("/auth/login", json={"email": "sunita@test.com", "password": "password123"})
    assert login.status_code == 200


# ---------------------------------------------------------------------------
# Invite-code flow (instant approval)
# ---------------------------------------------------------------------------


def test_invite_code_links_parent_instantly(client):
    teacher_token, teacher_id = _teacher(client)
    _batch_id, student_id = _batch_with_student(client, teacher_token)
    parent_token, _parent_id = _parent(client)

    invite = client.post(
        f"/teachers/students/{student_id}/invite-code", headers=auth_headers(teacher_token)
    ).json()
    assert invite["student_id"] == student_id

    link = client.post(
        "/parents/link-requests",
        json={"code": invite["code"], "relationship": "Mother"},
        headers=auth_headers(parent_token),
    )
    assert link.status_code == 201
    assert link.json()["status"] == "APPROVED"

    children = client.get("/parents/children", headers=auth_headers(parent_token)).json()
    assert len(children) == 1
    assert children[0]["student_id"] == student_id
    assert children[0]["relationship"] == "Mother"


def test_invite_code_cannot_be_reused(client):
    teacher_token, _ = _teacher(client)
    _batch_id, student_id = _batch_with_student(client, teacher_token)
    parent_token, _ = _parent(client)
    other_parent_token, _ = _parent(client, "parent2-p8@test.com")

    invite = client.post(
        f"/teachers/students/{student_id}/invite-code", headers=auth_headers(teacher_token)
    ).json()
    first = client.post(
        "/parents/link-requests", json={"code": invite["code"]}, headers=auth_headers(parent_token)
    )
    assert first.status_code == 201

    second = client.post(
        "/parents/link-requests", json={"code": invite["code"]}, headers=auth_headers(other_parent_token)
    )
    assert second.status_code == 400


def test_invalid_invite_code_rejected(client):
    parent_token, _ = _parent(client)
    resp = client.post(
        "/parents/link-requests", json={"code": "NOTREAL1"}, headers=auth_headers(parent_token)
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Pending-request flow (teacher approval required)
# ---------------------------------------------------------------------------


def test_pending_request_lifecycle_approve(client):
    teacher_token, _ = _teacher(client)
    _batch_id, student_id = _batch_with_student(client, teacher_token, "child-approve@test.com")
    parent_token, _ = _parent(client, "parent-approve@test.com")

    request = client.post(
        "/parents/link-requests",
        json={"student_email": "child-approve@test.com", "relationship": "Father"},
        headers=auth_headers(parent_token),
    )
    assert request.status_code == 201
    assert request.json()["status"] == "PENDING"
    link_id = request.json()["id"]

    # Not visible yet -- still PENDING.
    assert client.get("/parents/children", headers=auth_headers(parent_token)).json() == []
    progress_before = client.get(
        f"/parents/children/{student_id}/progress", headers=auth_headers(parent_token)
    )
    assert progress_before.status_code == 404

    pending = client.get("/teachers/link-requests", headers=auth_headers(teacher_token)).json()
    assert any(r["id"] == link_id for r in pending)

    approve = client.post(f"/teachers/link-requests/{link_id}/approve", headers=auth_headers(teacher_token))
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"

    children = client.get("/parents/children", headers=auth_headers(parent_token)).json()
    assert len(children) == 1 and children[0]["student_id"] == student_id

    progress_after = client.get(
        f"/parents/children/{student_id}/progress", headers=auth_headers(parent_token)
    )
    assert progress_after.status_code == 200
    assert progress_after.json()["student_id"] == student_id


def test_pending_request_lifecycle_reject(client):
    teacher_token, _ = _teacher(client)
    _batch_id, student_id = _batch_with_student(client, teacher_token, "child-reject@test.com")
    parent_token, _ = _parent(client, "parent-reject@test.com")

    request = client.post(
        "/parents/link-requests",
        json={"student_email": "child-reject@test.com"},
        headers=auth_headers(parent_token),
    ).json()

    reject = client.post(f"/teachers/link-requests/{request['id']}/reject", headers=auth_headers(teacher_token))
    assert reject.status_code == 200
    assert reject.json()["status"] == "REJECTED"

    # A rejected link must NEVER expose the child's data, ever.
    assert client.get("/parents/children", headers=auth_headers(parent_token)).json() == []
    progress = client.get(f"/parents/children/{student_id}/progress", headers=auth_headers(parent_token))
    assert progress.status_code == 404


def test_duplicate_pending_request_rejected(client):
    teacher_token, _ = _teacher(client)
    _batch_id, _student_id = _batch_with_student(client, teacher_token, "child-dup@test.com")
    parent_token, _ = _parent(client, "parent-dup@test.com")

    first = client.post(
        "/parents/link-requests", json={"student_email": "child-dup@test.com"}, headers=auth_headers(parent_token)
    )
    assert first.status_code == 201
    second = client.post(
        "/parents/link-requests", json={"student_email": "child-dup@test.com"}, headers=auth_headers(parent_token)
    )
    assert second.status_code == 409


def test_link_request_for_unknown_email_404s(client):
    parent_token, _ = _parent(client)
    resp = client.post(
        "/parents/link-requests", json={"student_email": "nobody@test.com"}, headers=auth_headers(parent_token)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Critical authorization -- "should fail" cases
# ---------------------------------------------------------------------------


def test_parent_cannot_view_another_students_data_by_id_guessing(client):
    """An APPROVED link for child A must not leak child B's data via ID guessing."""
    teacher_token, _ = _teacher(client)
    _b1, student_a = _batch_with_student(client, teacher_token, "child-a@test.com")
    _b2, student_b = _batch_with_student(client, teacher_token, "child-b@test.com", "Other Child")

    parent_token, _ = _parent(client, "guessing-parent@test.com")
    invite = client.post(
        f"/teachers/students/{student_a}/invite-code", headers=auth_headers(teacher_token)
    ).json()
    client.post("/parents/link-requests", json={"code": invite["code"]}, headers=auth_headers(parent_token))

    # Linked to A -- must be able to see A...
    ok = client.get(f"/parents/children/{student_a}/progress", headers=auth_headers(parent_token))
    assert ok.status_code == 200
    # ...but NOT B, despite knowing B's real user id.
    blocked = client.get(f"/parents/children/{student_b}/progress", headers=auth_headers(parent_token))
    assert blocked.status_code == 404


def test_teacher_cannot_approve_another_teachers_link_request(client):
    teacher_a_token, _ = _teacher(client, "teacher-a-p8@test.com")
    teacher_b_token, _ = _teacher(client, "teacher-b-p8@test.com")
    _batch_id, _student_id = _batch_with_student(client, teacher_a_token, "childx-p8@test.com")
    parent_token, _ = _parent(client, "parentx-p8@test.com")

    request = client.post(
        "/parents/link-requests", json={"student_email": "childx-p8@test.com"}, headers=auth_headers(parent_token)
    ).json()

    forbidden = client.post(
        f"/teachers/link-requests/{request['id']}/approve", headers=auth_headers(teacher_b_token)
    )
    assert forbidden.status_code == 404

    # Teacher B's pending list must not even list it.
    pending_b = client.get("/teachers/link-requests", headers=auth_headers(teacher_b_token)).json()
    assert all(r["id"] != request["id"] for r in pending_b)


def test_teacher_cannot_mark_syllabus_for_another_teachers_batch(client):
    teacher_a_token, _ = _teacher(client, "syllabus-a@test.com")
    teacher_b_token, _ = _teacher(client, "syllabus-b@test.com")
    batch_id, _student_id = _batch_with_student(client, teacher_a_token, "syllabus-child@test.com")

    subject = client.post("/subjects", json={"name": "Mathematics"}, headers=auth_headers(teacher_a_token)).json()
    topic = client.post(
        "/topics", json={"subject_id": subject["id"], "name": "Algebra"}, headers=auth_headers(teacher_a_token)
    ).json()

    forbidden = client.post(
        f"/syllabus/{topic['id']}/mark-complete",
        json={"batch_id": batch_id, "subject_id": subject["id"], "status": "COMPLETED"},
        headers=auth_headers(teacher_b_token),
    )
    assert forbidden.status_code == 404


def test_teacher_cannot_add_remark_for_student_not_in_their_batch(client):
    teacher_a_token, _ = _teacher(client, "remark-a@test.com")
    teacher_b_token, _ = _teacher(client, "remark-b@test.com")
    batch_a_id, student_id = _batch_with_student(client, teacher_a_token, "remark-child@test.com")

    forbidden = client.post(
        f"/students/{student_id}/remarks",
        json={"batch_id": batch_a_id, "remark_text": "Doing great", "category": "ACADEMIC"},
        headers=auth_headers(teacher_b_token),
    )
    assert forbidden.status_code == 404


def test_parent_cannot_generate_invite_code_or_approve_links(client):
    teacher_token, _ = _teacher(client, "role-check@test.com")
    _batch_id, student_id = _batch_with_student(client, teacher_token, "role-check-child@test.com")
    parent_token, _ = _parent(client, "role-check-parent@test.com")

    assert client.post(
        f"/teachers/students/{student_id}/invite-code", headers=auth_headers(parent_token)
    ).status_code == 403
    assert client.get("/teachers/link-requests", headers=auth_headers(parent_token)).status_code == 403


def test_remark_with_visible_to_parent_false_is_hidden_from_parent(client):
    teacher_token, _ = _teacher(client, "hidden-remark-teacher@test.com")
    batch_id, student_id = _batch_with_student(client, teacher_token, "hidden-remark-child@test.com")
    parent_token, _ = _parent(client, "hidden-remark-parent@test.com")

    invite = client.post(
        f"/teachers/students/{student_id}/invite-code", headers=auth_headers(teacher_token)
    ).json()
    client.post("/parents/link-requests", json={"code": invite["code"]}, headers=auth_headers(parent_token))

    client.post(
        f"/students/{student_id}/remarks",
        json={"batch_id": batch_id, "remark_text": "Visible remark", "category": "GENERAL", "visible_to_parent": True},
        headers=auth_headers(teacher_token),
    )
    client.post(
        f"/students/{student_id}/remarks",
        json={"batch_id": batch_id, "remark_text": "Private remark", "category": "BEHAVIOR", "visible_to_parent": False},
        headers=auth_headers(teacher_token),
    )

    progress = client.get(f"/parents/children/{student_id}/progress", headers=auth_headers(parent_token)).json()
    remark_texts = [r["remark_text"] for r in progress["remarks"]]
    assert "Visible remark" in remark_texts
    assert "Private remark" not in remark_texts

    # But the teacher's own view sees both.
    teacher_view = client.get(f"/students/{student_id}/remarks", headers=auth_headers(teacher_token)).json()
    assert len(teacher_view) == 2


# ---------------------------------------------------------------------------
# Syllabus completion percentage
# ---------------------------------------------------------------------------


def test_syllabus_completion_percentage_calculation(client):
    teacher_token, _ = _teacher(client, "syllabus-calc@test.com")
    batch_id, student_id = _batch_with_student(client, teacher_token, "syllabus-calc-child@test.com")
    parent_token, _ = _parent(client, "syllabus-calc-parent@test.com")

    subject = client.post("/subjects", json={"name": "Science"}, headers=auth_headers(teacher_token)).json()
    topics = [
        client.post(
            "/topics", json={"subject_id": subject["id"], "name": f"Chapter {i}"}, headers=auth_headers(teacher_token)
        ).json()
        for i in range(4)
    ]

    # Mark 1 of 4 complete, 1 in progress, 2 untouched.
    client.post(
        f"/syllabus/{topics[0]['id']}/mark-complete",
        json={"batch_id": batch_id, "subject_id": subject["id"], "status": "COMPLETED"},
        headers=auth_headers(teacher_token),
    )
    client.post(
        f"/syllabus/{topics[1]['id']}/mark-complete",
        json={"batch_id": batch_id, "subject_id": subject["id"], "status": "IN_PROGRESS"},
        headers=auth_headers(teacher_token),
    )

    checklist = client.get(
        f"/batches/{batch_id}/subjects/{subject['id']}/syllabus", headers=auth_headers(teacher_token)
    ).json()
    assert len(checklist) == 4
    statuses = {t["topic_id"]: t["status"] for t in checklist}
    assert statuses[topics[0]["id"]] == "COMPLETED"
    assert statuses[topics[1]["id"]] == "IN_PROGRESS"
    assert statuses[topics[2]["id"]] == "NOT_STARTED"

    invite = client.post(
        f"/teachers/students/{student_id}/invite-code", headers=auth_headers(teacher_token)
    ).json()
    client.post("/parents/link-requests", json={"code": invite["code"]}, headers=auth_headers(parent_token))

    progress = client.get(f"/parents/children/{student_id}/progress", headers=auth_headers(parent_token)).json()
    science = next(s for s in progress["syllabus"] if s["subject_id"] == subject["id"])
    assert science["total_topics"] == 4
    assert science["completed_topics"] == 1
    assert science["percentage"] == 25.0


# ---------------------------------------------------------------------------
# Teacher search
# ---------------------------------------------------------------------------


def test_teacher_search_by_locality_and_never_leaks_private_data(client):
    teacher_token, _ = _teacher(client, "search-teacher@test.com")
    client.patch(
        "/teachers/profile",
        json={"institute_name": "Bright Minds Academy", "bio": "10 years experience", "locality": "Andheri West", "city": "Mumbai"},
        headers=auth_headers(teacher_token),
    )
    batch_id, _student_id = _batch_with_student(client, teacher_token, "search-child@test.com")
    subject = client.post("/subjects", json={"name": "Physics", "grade": "10"}, headers=auth_headers(teacher_token)).json()
    client.post(
        "/assessments",
        json={"batch_id": batch_id, "subject_id": subject["id"], "title": "Test", "duration_minutes": 30, "total_marks": 10},
        headers=auth_headers(teacher_token),
    )
    client.patch(f"/batches/{batch_id}", json={"grade": "10"}, headers=auth_headers(teacher_token))

    # No auth required at all.
    results = client.get("/teachers/search", params={"locality": "Andheri"}).json()
    assert any(r["institute_name"] == "Bright Minds Academy" for r in results)

    match = next(r for r in results if r["institute_name"] == "Bright Minds Academy")
    assert "Physics" in match["subjects"]
    assert set(match.keys()) == {
        "teacher_id", "name", "institute_name", "bio", "locality", "city", "subjects", "grades",
    }

    no_match = client.get("/teachers/search", params={"locality": "Nonexistent Area"}).json()
    assert all(r["institute_name"] != "Bright Minds Academy" for r in no_match)

    subject_filtered = client.get("/teachers/search", params={"subject": "Physics"}).json()
    assert any(r["institute_name"] == "Bright Minds Academy" for r in subject_filtered)

    subject_miss = client.get("/teachers/search", params={"subject": "Chemistry"}).json()
    assert all(r["institute_name"] != "Bright Minds Academy" for r in subject_miss)
