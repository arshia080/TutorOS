import logging
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit_by_ip
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import CompleteGoogleSignupRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service
from app.services import google_oauth_service as google_svc
from app.services.auth_service import authenticate_user, issue_token, register_user
from app.services.google_oauth_service import GoogleAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = register_user(db, data)
    token = issue_token(user)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, data)
    token = issue_token(user)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


# ---------------------------------------------------------------------------
# Google Sign-In (OpenID Connect, authorization code flow)
# ---------------------------------------------------------------------------


def _login_error_redirect(error_code: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url}/login?{urlencode({'error': error_code})}")


@router.get("/google/login")
def google_login() -> RedirectResponse:
    try:
        state = google_svc.create_login_state()
        return RedirectResponse(google_svc.build_authorization_url(state))
    except GoogleAuthError as e:
        return _login_error_redirect(e.error_code)


@router.get("/google/link")
def google_link(current_user: User = Depends(get_current_user)) -> dict:
    """Returns the Google consent URL rather than redirecting directly --
    a plain browser navigation can't carry the Authorization header this
    endpoint needs, so the frontend calls this via an authenticated fetch()
    first, then does the actual page navigation itself with the URL we hand
    back. `google_login` above doesn't have this problem since it's reached
    by a fresh, not-yet-authenticated user for whom a direct redirect is
    exactly the right shape.
    """
    try:
        state = google_svc.create_link_state(current_user.id)
        return {"authorization_url": google_svc.build_authorization_url(state)}
    except GoogleAuthError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")


@router.get("/google/callback", dependencies=[Depends(rate_limit_by_ip("google_callback"))])
def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error is not None:
        logger.info("Google OAuth denied or errored client-side: %s", error)
        return _login_error_redirect("google_denied")

    if not code or not state:
        return _login_error_redirect("invalid_request")

    try:
        # CSRF check first, before any token exchange -- a forged or expired
        # state is rejected outright and nothing else in this function runs.
        state_payload = google_svc.decode_state(state)
        id_token = google_svc.exchange_code_for_id_token(code)
        identity = google_svc.verify_id_token(id_token)
    except GoogleAuthError as e:
        return _login_error_redirect(e.error_code)

    if not identity.email_verified:
        logger.warning("Google login rejected: email not verified (%s)", identity.email)
        return _login_error_redirect("email_not_verified")

    if state_payload["purpose"] == google_svc.STATE_PURPOSE_LINK:
        try:
            auth_service.link_google_account(db, uuid.UUID(state_payload["user_id"]), identity)
        except HTTPException as e:
            return RedirectResponse(
                f"{settings.frontend_url}/dashboard/settings?{urlencode({'google_link_error': e.detail})}"
            )
        return RedirectResponse(f"{settings.frontend_url}/dashboard/settings?google_linked=1")

    # purpose == login
    try:
        user = auth_service.find_user_for_google_login(db, identity)
    except auth_service.GoogleLoginCollision:
        return _login_error_redirect("google_account_exists_local")

    if user is None:
        pending_token = google_svc.create_pending_signup_token(identity)
        return RedirectResponse(
            f"{settings.frontend_url}/auth/google/choose-role?{urlencode({'token': pending_token})}"
        )

    token = issue_token(user)
    return RedirectResponse(f"{settings.frontend_url}/auth/google/complete#{urlencode({'token': token})}")


@router.post("/google/complete-signup", response_model=TokenResponse, status_code=201)
def complete_google_signup(data: CompleteGoogleSignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        identity = google_svc.decode_pending_signup_token(data.pending_token)
    except GoogleAuthError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This sign-up link has expired. Please try again.")

    user = auth_service.complete_google_signup(
        db, identity, UserRole(data.role), phone=data.phone, locality=data.locality
    )
    token = issue_token(user)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))
