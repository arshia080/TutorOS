"""Google Sign-In (OpenID Connect).

Backend token verification and account-matching are the highest-risk part of
this phase -- a mistake here is an account-takeover vulnerability. Every
test that stands in for "a real Google login happened" does so by
monkeypatching `google_oauth_service.exchange_code_for_id_token` and
`.verify_id_token` (the two functions that talk to Google's real servers) --
never by fabricating a real ID token, and never by skipping CSRF/state
verification, which always runs against the real signing logic.
"""

from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import settings
from app.models.user import User
from app.services import google_oauth_service
from app.services.google_oauth_service import GoogleIdentity
from tests.conftest import auth_headers, register


@pytest.fixture(autouse=True)
def _configure_google(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret")


def _start_login_state(client) -> str:
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert location.startswith("https://accounts.google.com/")
    return parse_qs(urlparse(location).query)["state"][0]


def _fake_google(monkeypatch, identity: GoogleIdentity, exchange_called: list | None = None):
    def fake_exchange(code: str) -> str:
        if exchange_called is not None:
            exchange_called.append(code)
        return "fake-id-token"

    monkeypatch.setattr(google_oauth_service, "exchange_code_for_id_token", fake_exchange)
    monkeypatch.setattr(google_oauth_service, "verify_id_token", lambda token: identity)


def _query(location: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}


def _fragment(location: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(location).fragment).items()}


# ---------------------------------------------------------------------------
# New user: pending signup -> role selection -> account creation
# ---------------------------------------------------------------------------


def test_new_google_user_requires_role_selection_then_completes(client, monkeypatch, db_session):
    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-new-1", email="newgoogle@test.com", email_verified=True, name="New Googler")
    _fake_google(monkeypatch, identity)

    callback = client.get(f"/auth/google/callback?code=abc123&state={state}", follow_redirects=False)
    assert callback.status_code in (302, 307)
    location = callback.headers["location"]
    assert location.startswith(f"{settings.frontend_url}/auth/google/choose-role")
    pending_token = _query(location)["token"]

    # No user was created yet -- role is still unknown.
    assert db_session.query(User).filter(User.email == "newgoogle@test.com").first() is None

    complete = client.post(
        "/auth/google/complete-signup", json={"pending_token": pending_token, "role": "STUDENT"}
    )
    assert complete.status_code == 201
    body = complete.json()
    assert body["user"]["email"] == "newgoogle@test.com"
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["auth_provider"] == "GOOGLE"

    me = client.get("/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "newgoogle@test.com"


def test_google_signup_cannot_self_select_admin_role(client, monkeypatch):
    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-admin-try", email="wannabeadmin@test.com", email_verified=True, name="X")
    _fake_google(monkeypatch, identity)
    callback = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    pending_token = _query(callback.headers["location"])["token"]

    resp = client.post("/auth/google/complete-signup", json={"pending_token": pending_token, "role": "ADMIN"})
    assert resp.status_code == 422  # not a legal choice for this endpoint's schema


# ---------------------------------------------------------------------------
# Existing GOOGLE-provider user: normal login
# ---------------------------------------------------------------------------


def test_login_for_existing_google_user(client, monkeypatch):
    # Create the account the same way a real one would come to exist.
    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-existing-1", email="existinggoogle@test.com", email_verified=True, name="Returning Googler")
    _fake_google(monkeypatch, identity)
    first = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    pending_token = _query(first.headers["location"])["token"]
    client.post("/auth/google/complete-signup", json={"pending_token": pending_token, "role": "TEACHER"})

    # Second login, same Google identity.
    state2 = _start_login_state(client)
    second = client.get(f"/auth/google/callback?code=xyz&state={state2}", follow_redirects=False)
    assert second.status_code in (302, 307)
    location = second.headers["location"]
    assert location.startswith(f"{settings.frontend_url}/auth/google/complete#")
    token = _fragment(location)["token"]

    me = client.get("/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "existinggoogle@test.com"
    assert me.json()["role"] == "TEACHER"


# ---------------------------------------------------------------------------
# email_verified == false must never create or link an account
# ---------------------------------------------------------------------------


def test_unverified_email_rejected_no_account_created(client, monkeypatch, db_session):
    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-unverified", email="unverified@test.com", email_verified=False, name="Nope")
    _fake_google(monkeypatch, identity)

    resp = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _query(resp.headers["location"]) == {"error": "email_not_verified"}
    assert db_session.query(User).filter(User.email == "unverified@test.com").first() is None


# ---------------------------------------------------------------------------
# LOCAL account + Google email collision -- must never be silently merged
# ---------------------------------------------------------------------------


def test_google_login_with_existing_local_email_is_rejected_not_merged(client, monkeypatch, db_session):
    register(client, "Local Teacher", "collision@test.com", role="TEACHER")

    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-collision", email="collision@test.com", email_verified=True, name="Impersonator?")
    _fake_google(monkeypatch, identity)

    resp = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _query(resp.headers["location"]) == {"error": "google_account_exists_local"}

    user = db_session.query(User).filter(User.email == "collision@test.com").first()
    assert user.auth_provider.value == "LOCAL"
    assert user.google_id is None  # never auto-linked based on email match alone


def test_local_user_can_explicitly_link_google_account(client, monkeypatch, db_session):
    reg = register(client, "Linker", "linker@test.com", role="TEACHER")
    token = reg["access_token"]

    link_start = client.get("/auth/google/link", headers=auth_headers(token))
    assert link_start.status_code == 200
    state = parse_qs(urlparse(link_start.json()["authorization_url"]).query)["state"][0]

    identity = GoogleIdentity(sub="google-sub-link-1", email="linker@test.com", email_verified=True, name="Linker")
    _fake_google(monkeypatch, identity)

    resp = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "google_linked=1" in resp.headers["location"]

    user = db_session.query(User).filter(User.email == "linker@test.com").first()
    assert user.google_id == "google-sub-link-1"
    assert user.auth_provider.value == "LOCAL"  # linking doesn't change the primary provider

    # Now a Google login with that identity logs into the SAME account.
    state2 = _start_login_state(client)
    login_resp = client.get(f"/auth/google/callback?code=xyz&state={state2}", follow_redirects=False)
    token2 = _fragment(login_resp.headers["location"])["token"]
    me = client.get("/auth/me", headers=auth_headers(token2))
    assert me.json()["email"] == "linker@test.com"


def test_link_google_account_email_mismatch_rejected(client, monkeypatch, db_session):
    reg = register(client, "Mismatch User", "mismatch@test.com", role="TEACHER")
    token = reg["access_token"]

    link_start = client.get("/auth/google/link", headers=auth_headers(token))
    state = parse_qs(urlparse(link_start.json()["authorization_url"]).query)["state"][0]

    identity = GoogleIdentity(sub="google-sub-other", email="totally-different@test.com", email_verified=True, name="Other")
    _fake_google(monkeypatch, identity)

    resp = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "google_link_error" in resp.headers["location"]

    user = db_session.query(User).filter(User.email == "mismatch@test.com").first()
    assert user.google_id is None


# ---------------------------------------------------------------------------
# CSRF: a forged/tampered/missing state must be rejected before any exchange
# ---------------------------------------------------------------------------


def test_forged_state_rejected_before_any_token_exchange(client, monkeypatch):
    exchange_calls: list = []
    identity = GoogleIdentity(sub="whatever", email="whatever@test.com", email_verified=True, name="X")
    _fake_google(monkeypatch, identity, exchange_called=exchange_calls)

    resp = client.get("/auth/google/callback?code=abc123&state=totally-forged-not-a-jwt", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _query(resp.headers["location"]) == {"error": "invalid_state"}
    assert exchange_calls == []  # code exchange must never have been attempted


def test_missing_state_rejected(client):
    resp = client.get("/auth/google/callback?code=abc123", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _query(resp.headers["location"]) == {"error": "invalid_request"}


def test_expired_state_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_state_expire_minutes", -1)
    state = _start_login_state(client)
    resp = client.get(f"/auth/google/callback?code=abc123&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _query(resp.headers["location"]) == {"error": "invalid_state"}


# ---------------------------------------------------------------------------
# Role-based authorization must work identically regardless of login method
# ---------------------------------------------------------------------------


def test_google_issued_jwt_has_identical_authorization_to_password_jwt(client, monkeypatch):
    state = _start_login_state(client)
    identity = GoogleIdentity(sub="google-sub-teacher-1", email="googleteacher@test.com", email_verified=True, name="G Teacher")
    _fake_google(monkeypatch, identity)
    callback = client.get(f"/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    pending_token = _query(callback.headers["location"])["token"]
    signup = client.post("/auth/google/complete-signup", json={"pending_token": pending_token, "role": "TEACHER"})
    google_token = signup.json()["access_token"]

    local_reg = register(client, "Local Teacher 2", "localteacher2@test.com", role="TEACHER")
    local_token = local_reg["access_token"]

    # Same teacher-only action, same result, regardless of how the JWT was issued.
    google_batch = client.post("/batches", json={"name": "Google Teacher's Batch"}, headers=auth_headers(google_token))
    local_batch = client.post("/batches", json={"name": "Local Teacher's Batch"}, headers=auth_headers(local_token))
    assert google_batch.status_code == 201
    assert local_batch.status_code == 201

    google_dashboard = client.get("/teachers/dashboard", headers=auth_headers(google_token))
    local_dashboard = client.get("/teachers/dashboard", headers=auth_headers(local_token))
    assert google_dashboard.status_code == 200
    assert local_dashboard.status_code == 200
