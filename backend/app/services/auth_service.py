"""Authentication service: registration, login and principal resolution."""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import Role, create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import UserRepository
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserRead


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def register(self, payload: UserCreate) -> UserRead:
        if await self._user_repo.get_by_email(payload.email):
            raise ConflictError("An account with this email already exists.")

        user = await self._user_repo.add(
            User(
                email=payload.email.lower(),
                full_name=payload.full_name,
                hashed_password=hash_password(payload.password),
                role=payload.role,
            )
        )
        await self._user_repo.commit()
        return UserRead.model_validate(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self._user_repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")

        token = create_access_token(user.id, role=user.role)
        return TokenResponse(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserRead.model_validate(user),
        )

    async def ensure_mock_user(self) -> User:
        """MVP helper: return (creating if needed) the demo principal."""
        user = await self._user_repo.get_by_email(settings.MOCK_AUTH_EMAIL)
        if user is None:
            user = await self._user_repo.add(
                User(
                    email=settings.MOCK_AUTH_EMAIL,
                    full_name="Demo User",
                    hashed_password=hash_password("demo-password"),
                    role=Role(settings.MOCK_AUTH_ROLE),
                )
            )
            await self._user_repo.commit()
        return user
