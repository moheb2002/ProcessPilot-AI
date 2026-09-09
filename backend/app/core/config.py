"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Application -----
    APP_NAME: str = "ProcessPilot AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["local", "dev", "staging", "production"] = "local"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ----- Security -----
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    # MVP toggle: when true a default demo user is injected if no token is supplied.
    MOCK_AUTH_ENABLED: bool = True
    MOCK_AUTH_EMAIL: str = "demo@processpilot.ai"
    MOCK_AUTH_ROLE: str = "admin"

    # ----- CORS -----
    # Comma-separated; parsed by the `cors_origins` property. Kept as a plain string
    # because pydantic-settings tries to JSON-decode list-typed env vars.
    CORS_ORIGINS: str = "http://localhost:3000"

    # ----- Rate limiting -----
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ----- Database -----
    DATABASE_URL: str = "sqlite+aiosqlite:///./processpilot.db"
    DB_ECHO: bool = False

    # ----- Storage (MVP: local disk, extensible to Azure Blob) -----
    STORAGE_BACKEND: Literal["local", "azure_blob"] = "local"
    LOCAL_STORAGE_PATH: Path = BASE_DIR / "storage"
    AZURE_STORAGE_CONNECTION_STRING: str | None = None
    AZURE_STORAGE_CONTAINER: str = "processpilot-documents"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS: str = ".pdf,.docx,.txt"

    # ----- Azure OpenAI -----
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    AZURE_OPENAI_MAX_TOKENS: int = 4096
    AZURE_OPENAI_TEMPERATURE: float = 0.2
    AZURE_OPENAI_MAX_RETRIES: int = 3
    AZURE_OPENAI_TIMEOUT_SECONDS: float = 60.0
    # When true (or when credentials are missing) deterministic stub responses are used.
    USE_MOCK_LLM: bool = False

    # ----- Observability -----
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    APPLICATIONINSIGHTS_CONNECTION_STRING: str | None = None

    @field_validator("LOCAL_STORAGE_PATH", mode="after")
    @classmethod
    def _absolute_storage_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BASE_DIR / value).resolve()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_upload_extensions(self) -> set[str]:
        return {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in self.ALLOWED_UPLOAD_EXTENSIONS.split(",")
            if ext.strip()
        }

    @property
    def azure_openai_configured(self) -> bool:
        return bool(self.AZURE_OPENAI_ENDPOINT)

    @property
    def llm_mock_mode(self) -> bool:
        """Mock mode is active explicitly or when Azure OpenAI is not configured."""
        return self.USE_MOCK_LLM or not self.azure_openai_configured


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
