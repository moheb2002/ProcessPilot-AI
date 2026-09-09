"""User and authentication schemas."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.security import Role
from app.schemas.common import APIModel, TimestampedSchema


class UserCreate(APIModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.EMPLOYEE


class UserRead(TimestampedSchema):
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class CurrentUser(APIModel):
    """Authenticated principal resolved from the JWT (or mock auth)."""

    id: str
    email: EmailStr
    full_name: str
    role: Role
