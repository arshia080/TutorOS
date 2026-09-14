import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.parent import ParentProfile
from app.models.user import AuthProvider, User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.google_oauth_service import GoogleIdentity

logger = logging.getLogger(__name__)


def register_user(db: Session, data: RegisterRequest) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing is not None:
        # Email only -- never log a password or password_hash anywhere in this module.
        logger.info("Registration rejected (duplicate email): %s", data.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        auth_provider=AuthProvider.LOCAL,
    )
    db.add(user)
    db.flush()

    if user.role == UserRole.PARENT:
        db.add(ParentProfile(user_id=user.id, phone=data.phone, locality=data.locality))

    db.commit()
    db.refresh(user)
    logger.info("User registered: id=%s email=%s role=%s", user.id, user.email, user.role.value)
    return user


def authenticate_user(db: Session, data: LoginRequest) -> User:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )
    user = db.query(User).filter(User.email == data.email).first()
    # A GOOGLE-only account has no password_hash at all -- never pass None into
    # verify_password (passlib raises on a non-str hash rather than just failing).
    if user is None or user.password_hash is None or not verify_password(data.password, user.password_hash):
        logger.warning("Login failed for email: %s", data.email)
        raise invalid_credentials
    logger.info("User logged in: id=%s email=%s", user.id, user.email)
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=str(user.id))


# ---------------------------------------------------------------------------
# Google Sign-In account matching
#
# See docs/PROGRESS.md for the full account-matching decision writeup. Short
# version: an email match against an existing LOCAL account is NEVER treated
# as proof of identity by itself -- that's exactly the account-takeover shape
# this phase was warned against. Linking Google to an existing account only
# ever happens through the separate, explicitly-authenticated `link` flow.
# ---------------------------------------------------------------------------


class GoogleLoginCollision(Exception):
    """Raised when a GOOGLE sign-in matches an email already registered
    LOCAL (no google_id linked yet) -- never silently merged.
    """


def find_user_for_google_login(db: Session, identity: GoogleIdentity) -> User | None:
    """Returns the user to log in, or None if this is a brand-new signup.
    Raises GoogleLoginCollision if the email belongs to an existing account
    that hasn't linked Google.
    """
    by_google_id = db.query(User).filter(User.google_id == identity.sub).first()
    if by_google_id is not None:
        return by_google_id

    by_email = db.query(User).filter(User.email == identity.email).first()
    if by_email is not None:
        # google_id is None here (the by_google_id lookup above would have
        # caught it otherwise) -- an existing account with Google not linked.
        raise GoogleLoginCollision()

    return None  # genuinely new -- caller routes to role selection


def complete_google_signup(db: Session, identity: GoogleIdentity, role: UserRole, phone: str | None, locality: str | None) -> User:
    """Creates a new GOOGLE-provider account. Re-checks for a race (two tabs
    completing signup, or a LOCAL account registered in the meantime) rather
    than trusting the caller already confirmed this is safe.
    """
    existing = db.query(User).filter(
        (User.email == identity.email) | (User.google_id == identity.sub)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        name=identity.name,
        email=identity.email,
        password_hash=None,
        role=role,
        auth_provider=AuthProvider.GOOGLE,
        google_id=identity.sub,
    )
    db.add(user)
    db.flush()

    if role == UserRole.PARENT:
        db.add(ParentProfile(user_id=user.id, phone=phone, locality=locality))

    db.commit()
    db.refresh(user)
    logger.info("User registered via Google: id=%s email=%s role=%s", user.id, user.email, user.role.value)
    return user


def link_google_account(db: Session, user_id: uuid.UUID, identity: GoogleIdentity) -> User:
    """Links Google as an additional sign-in method for an already-authenticated
    user. The caller (the route) only reaches here after the user completed a
    real Google consent screen while already logged in via a valid session --
    this is the "explicitly confirm" step, not a bare email match.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.email != identity.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That Google account's email doesn't match your account's email",
        )

    conflict = db.query(User).filter(User.google_id == identity.sub, User.id != user.id).first()
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That Google account is already linked to another user"
        )

    user.google_id = identity.sub
    db.commit()
    db.refresh(user)
    logger.info("Google account linked: id=%s email=%s", user.id, user.email)
    return user
