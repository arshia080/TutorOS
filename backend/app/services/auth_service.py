import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.parent import ParentProfile
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest

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
    if user is None or not verify_password(data.password, user.password_hash):
        logger.warning("Login failed for email: %s", data.email)
        raise invalid_credentials
    logger.info("User logged in: id=%s email=%s", user.id, user.email)
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=str(user.id))
