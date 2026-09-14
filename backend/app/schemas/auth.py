from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.user import UserRead


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.STUDENT
    # Only used when role == PARENT; ignored otherwise.
    phone: str | None = Field(default=None, max_length=30)
    locality: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


# Deliberately excludes ADMIN -- a first-time Google sign-in should never be
# able to self-select an administrative role, same reasoning a public signup
# form shouldn't offer it (the existing /auth/register endpoint accepting any
# UserRole including ADMIN is a pre-existing gap, unrelated to this phase and
# not touched here).
GoogleSignupRole = Literal["TEACHER", "STUDENT", "PARENT"]


class CompleteGoogleSignupRequest(BaseModel):
    pending_token: str
    role: GoogleSignupRole
    phone: str | None = Field(default=None, max_length=30)
    locality: str | None = Field(default=None, max_length=255)
