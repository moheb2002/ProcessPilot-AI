"""Password hashing, JWT issuance/verification and RBAC role definitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


#: Role inheritance — a role grants every permission of the roles it contains.
ROLE_HIERARCHY: dict[Role, set[Role]] = {
    Role.ADMIN: {Role.ADMIN, Role.MANAGER, Role.EMPLOYEE},
    Role.MANAGER: {Role.MANAGER, Role.EMPLOYEE},
    Role.EMPLOYEE: {Role.EMPLOYEE},
}


def role_satisfies(actual: Role, required: Role) -> bool:
    return required in ROLE_HIERARCHY.get(actual, set())


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def create_access_token(
    subject: str,
    *,
    role: Role | str = Role.EMPLOYEE,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": subject,
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME,
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc
