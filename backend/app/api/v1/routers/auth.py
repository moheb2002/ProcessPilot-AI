"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUserDep
from app.schemas.user import CurrentUser, LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(payload: UserCreate, auth_service: AuthServiceDep) -> UserRead:
    return await auth_service.register(payload)


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for a JWT")
async def login(payload: LoginRequest, auth_service: AuthServiceDep) -> TokenResponse:
    return await auth_service.login(payload)


@router.get("/me", response_model=CurrentUser, summary="Return the authenticated principal")
async def me(user: CurrentUserDep) -> CurrentUser:
    return user
