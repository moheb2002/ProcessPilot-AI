"""Unit tests for password hashing, JWT handling and RBAC."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    Role,
    create_access_token,
    decode_access_token,
    hash_password,
    role_satisfies,
    verify_password,
)


def test_password_hash_is_salted_and_verifiable() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip_preserves_claims() -> None:
    token = create_access_token("user-123", role=Role.MANAGER)
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "manager"


def test_expired_token_is_rejected() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-10))
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-123")
    with pytest.raises(AuthenticationError):
        decode_access_token(token + "tampered")


@pytest.mark.parametrize(
    ("actual", "required", "expected"),
    [
        (Role.ADMIN, Role.EMPLOYEE, True),
        (Role.ADMIN, Role.MANAGER, True),
        (Role.MANAGER, Role.EMPLOYEE, True),
        (Role.MANAGER, Role.ADMIN, False),
        (Role.EMPLOYEE, Role.MANAGER, False),
        (Role.EMPLOYEE, Role.EMPLOYEE, True),
    ],
)
def test_role_hierarchy(actual: Role, required: Role, expected: bool) -> None:
    assert role_satisfies(actual, required) is expected
