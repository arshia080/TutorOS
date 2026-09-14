"""Google Sign-In via OpenID Connect (authorization code flow).

Three signed, short-lived JWTs do all the trust-boundary work here, all
using the app's own `jwt_secret_key` (the same signing key session tokens
use -- this is still "the app's own JWT issuance," just for different
purposes than a session):

- `state`: a CSRF nonce round-tripped through Google. Encodes `purpose`
  ("google_login" or "google_link") and, for linking, the already-authenticated
  user's id. Verified on callback *before* anything else happens -- a forged
  or expired state is rejected outright (see `decode_state`).
- pending-signup token: issued only after we've already verified a real
  Google ID token server-side, for the one case where we deliberately don't
  create a user yet (first-time sign-in, role unknown). Carries the verified
  `sub`/`email`/`name` so `POST /auth/google/complete-signup` doesn't have to
  trust anything the client sends about who this is -- only which role they
  picked.

None of this ever trusts an ID token the frontend hands us directly: the
frontend never sees a Google ID token at all in this flow. Google redirects
the browser straight to our backend callback with a `code`; the code is
exchanged for tokens server-to-server, and the ID token is verified
server-side against Google's live JWKS before any account decision is made.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

STATE_PURPOSE_LOGIN = "google_login"
STATE_PURPOSE_LINK = "google_link"
PENDING_SIGNUP_PURPOSE = "google_pending_signup"


class GoogleAuthError(Exception):
    """Anything that should abort the flow with a specific, safe-to-show reason."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


def _require_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise GoogleAuthError("google_not_configured")


def _encode_jwt(claims: dict, expire_minutes: int) -> str:
    payload = {**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_jwt(token: str, expected_purpose: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise GoogleAuthError("invalid_state") from e
    if payload.get("purpose") != expected_purpose:
        raise GoogleAuthError("invalid_state")
    return payload


def create_login_state() -> str:
    return _encode_jwt(
        {"purpose": STATE_PURPOSE_LOGIN, "nonce": uuid.uuid4().hex},
        settings.google_oauth_state_expire_minutes,
    )


def create_link_state(user_id: uuid.UUID) -> str:
    return _encode_jwt(
        {"purpose": STATE_PURPOSE_LINK, "user_id": str(user_id), "nonce": uuid.uuid4().hex},
        settings.google_oauth_state_expire_minutes,
    )


def decode_state(state: str) -> dict:
    """Raises GoogleAuthError("invalid_state") for anything forged, tampered
    with, expired, or missing entirely -- the CSRF check every callback must
    pass before code exchange even begins.
    """
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise GoogleAuthError("invalid_state") from e
    if payload.get("purpose") not in (STATE_PURPOSE_LOGIN, STATE_PURPOSE_LINK):
        raise GoogleAuthError("invalid_state")
    return payload


def build_authorization_url(state: str) -> str:
    _require_configured()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_id_token(code: str) -> str:
    """Server-to-server token exchange. Returns the raw (still-unverified)
    ID token JWT string; verify_id_token() does the actual verification.
    """
    _require_configured()
    try:
        response = httpx.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Google token exchange failed: %s", e)
        raise GoogleAuthError("google_exchange_failed") from e

    id_token = response.json().get("id_token")
    if not id_token:
        raise GoogleAuthError("google_exchange_failed")
    return id_token


def _fetch_jwks() -> list[dict]:
    try:
        response = httpx.get(GOOGLE_JWKS_ENDPOINT, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Fetching Google JWKS failed: %s", e)
        raise GoogleAuthError("google_verification_failed") from e
    return response.json().get("keys", [])


def verify_id_token(id_token: str) -> GoogleIdentity:
    """Verifies the ID token's signature against Google's live JWKS, plus
    audience and issuer -- never trust an ID token without doing this.
    """
    _require_configured()
    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise GoogleAuthError("invalid_google_token") from e

    kid = unverified_header.get("kid")
    matching_key = next((k for k in _fetch_jwks() if k.get("kid") == kid), None)
    if matching_key is None:
        raise GoogleAuthError("invalid_google_token")

    try:
        claims = jwt.decode(
            id_token,
            matching_key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=None,  # validated manually below: jose only accepts one issuer string
        )
    except JWTError as e:
        raise GoogleAuthError("invalid_google_token") from e

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleAuthError("invalid_google_token")

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleAuthError("invalid_google_token")

    return GoogleIdentity(
        sub=sub,
        email=email,
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name") or email.split("@")[0],
    )


def create_pending_signup_token(identity: GoogleIdentity) -> str:
    return _encode_jwt(
        {
            "purpose": PENDING_SIGNUP_PURPOSE,
            "sub": identity.sub,
            "email": identity.email,
            "name": identity.name,
        },
        settings.google_oauth_state_expire_minutes,
    )


def decode_pending_signup_token(token: str) -> GoogleIdentity:
    payload = _decode_jwt(token, PENDING_SIGNUP_PURPOSE)
    return GoogleIdentity(sub=payload["sub"], email=payload["email"], email_verified=True, name=payload["name"])
