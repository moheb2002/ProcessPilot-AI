"""Integration tests for registration, login and RBAC enforcement."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CREDENTIALS = {
    "email": "manager@contoso.com",
    "full_name": "Morgan Manager",
    "password": "Str0ngPassw0rd!",
    "role": "manager",
}


async def test_register_then_login_returns_token(client: AsyncClient) -> None:
    registered = await client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert registered.status_code == 201
    assert registered.json()["role"] == "manager"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_duplicate_registration_conflicts(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    duplicate = await client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert duplicate.status_code == 409


async def test_login_with_wrong_password_is_unauthorized(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": "not-the-password"},
    )
    assert response.status_code == 401


async def test_me_returns_mock_user_without_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "demo@processpilot.ai"


async def test_me_returns_token_subject_when_authenticated(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=CREDENTIALS)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": CREDENTIALS["email"], "password": CREDENTIALS["password"]},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == CREDENTIALS["email"]


async def test_invalid_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_employee_cannot_delete_analysis(client: AsyncClient) -> None:
    employee = {
        "email": "employee@contoso.com",
        "full_name": "Evan Employee",
        "password": "Str0ngPassw0rd!",
        "role": "employee",
    }
    await client.post("/api/v1/auth/register", json=employee)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": employee["email"], "password": employee["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.delete("/api/v1/process/analyses/any-id", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
