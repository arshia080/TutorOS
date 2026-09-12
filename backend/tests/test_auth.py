def _register(client, email="rahul@example.com", password="password123"):
    return client.post(
        "/auth/register",
        json={"name": "Rahul Sharma", "email": email, "password": password, "role": "STUDENT"},
    )


def test_register_success(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "rahul@example.com"
    assert "access_token" in body


def test_register_duplicate_email_rejected(client):
    _register(client)
    response = _register(client)
    assert response.status_code == 409


def test_login_correct_password(client):
    _register(client, email="ananya@example.com", password="password123")
    response = client.post(
        "/auth/login", json={"email": "ananya@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_incorrect_password(client):
    _register(client, email="aryan@example.com", password="password123")
    response = client.post(
        "/auth/login", json={"email": "aryan@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_protected_route_without_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_protected_route_with_valid_token(client):
    register_response = _register(client, email="priya@example.com", password="password123")
    token = register_response.json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "priya@example.com"


def test_protected_route_with_invalid_token(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
