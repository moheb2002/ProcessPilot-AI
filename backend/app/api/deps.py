"""FastAPI dependency wiring: auth principal, repositories and services."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import Role, decode_access_token, role_satisfies
from app.db.session import get_db_session
from app.repositories import (
    AnalysisRepository,
    AuditRepository,
    DocumentRepository,
    ProcessRepository,
    UserRepository,
)
from app.schemas.user import CurrentUser
from app.services import (
    AnalysisService,
    AuthService,
    AzureOpenAIClient,
    DocumentService,
    LLMClient,
    MockLLMClient,
    ReportService,
    StorageBackend,
    get_storage_backend,
)

_bearer_scheme = HTTPBearer(auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


# --------------------------------------------------------------------------- #
# Infrastructure singletons
# --------------------------------------------------------------------------- #
@lru_cache
def get_llm_client() -> LLMClient:
    if settings.llm_mock_mode:
        return MockLLMClient()
    return AzureOpenAIClient()


@lru_cache
def get_storage() -> StorageBackend:
    return get_storage_backend()


LLM = Annotated[LLMClient, Depends(get_llm_client)]
Storage = Annotated[StorageBackend, Depends(get_storage)]


# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #
def get_user_repo(session: DBSession) -> UserRepository:
    return UserRepository(session)


def get_analysis_repo(session: DBSession) -> AnalysisRepository:
    return AnalysisRepository(session)


def get_process_repo(session: DBSession) -> ProcessRepository:
    return ProcessRepository(session)


def get_document_repo(session: DBSession) -> DocumentRepository:
    return DocumentRepository(session)


def get_audit_repo(session: DBSession) -> AuditRepository:
    return AuditRepository(session)


# --------------------------------------------------------------------------- #
# Authentication / RBAC
# --------------------------------------------------------------------------- #
def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> AuthService:
    return AuthService(user_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> CurrentUser:
    """Resolve the caller from a JWT, falling back to the demo user when mock auth is on."""
    if credentials is None or not credentials.credentials:
        if settings.MOCK_AUTH_ENABLED:
            user = await auth_service.ensure_mock_user()
            return CurrentUser.model_validate(user, from_attributes=True)
        raise AuthenticationError()

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Token is missing the subject claim.")

    user = await user_repo.get(str(subject))
    if user is None or not user.is_active:
        raise AuthenticationError("The account for this token no longer exists.")
    return CurrentUser.model_validate(user, from_attributes=True)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(required: Role):
    """Dependency factory enforcing a minimum role (honours the role hierarchy)."""

    async def _guard(user: CurrentUserDep) -> CurrentUser:
        if not role_satisfies(user.role, required):
            raise AuthorizationError(f"This action requires the '{required}' role.")
        return user

    return _guard


# --------------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------------- #
def get_analysis_service(
    llm: LLM,
    analysis_repo: Annotated[AnalysisRepository, Depends(get_analysis_repo)],
    process_repo: Annotated[ProcessRepository, Depends(get_process_repo)],
    document_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> AnalysisService:
    return AnalysisService(
        llm=llm,
        analysis_repo=analysis_repo,
        process_repo=process_repo,
        document_repo=document_repo,
        audit_repo=audit_repo,
    )


def get_report_service(
    llm: LLM,
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ReportService:
    return ReportService(llm=llm, analysis_service=analysis_service, audit_repo=audit_repo)


def get_document_service(
    storage: Storage,
    document_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> DocumentService:
    return DocumentService(storage=storage, document_repo=document_repo, audit_repo=audit_repo)


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
class Pagination:
    # Plain `Query` defaults (not `Annotated`) because this module uses
    # `from __future__ import annotations`, which would leave nested Annotated as a ForwardRef.
    def __init__(
        self,
        limit: int = Query(default=20, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
