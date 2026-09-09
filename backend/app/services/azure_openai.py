"""Azure OpenAI chat client with retry, JSON-mode parsing and token accounting."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol
from urllib.parse import urlsplit

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.schemas.agent import TokenUsage

logger = get_logger(__name__)


def _token_scope(endpoint: str) -> str:
    if _is_foundry_endpoint(endpoint):
        return "https://ai.azure.com/.default"
    return "https://cognitiveservices.azure.com/.default"


def _is_foundry_endpoint(endpoint: str) -> bool:
    return urlsplit(endpoint).hostname is not None and urlsplit(endpoint).hostname.endswith(
        ".services.ai.azure.com"
    )


def _foundry_inference_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    return f"{parsed.scheme}://{parsed.netloc}/openai/v1/"


class LLMClient(Protocol):
    """Abstraction so agents can be tested without a live Azure OpenAI resource."""

    async def complete_json(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[dict[str, Any], TokenUsage]: ...

    async def complete_text(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[str, TokenUsage]: ...


class _RetryableLLMError(RuntimeError):
    """Internal marker for transient failures worth retrying."""


class AzureOpenAIClient:
    """Thin async wrapper over the Azure OpenAI chat completions API."""

    def __init__(self) -> None:
        if not settings.azure_openai_configured:
            raise LLMError("Azure OpenAI endpoint is not configured.")

        from azure.identity import AzureCliCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI, AsyncOpenAI

        endpoint = str(settings.AZURE_OPENAI_ENDPOINT)
        token_provider = get_bearer_token_provider(
            AzureCliCredential(),
            _token_scope(endpoint),
        )
        self._token_provider = token_provider if _is_foundry_endpoint(endpoint) else None
        if self._token_provider:
            self._client = AsyncOpenAI(
                base_url=_foundry_inference_endpoint(endpoint),
                api_key=self._token_provider(),
                timeout=settings.AZURE_OPENAI_TIMEOUT_SECONDS,
                max_retries=0,
            )
        else:
            self._client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                timeout=settings.AZURE_OPENAI_TIMEOUT_SECONDS,
                max_retries=0,  # retries are handled by tenacity below
            )
        self._deployment = settings.AZURE_OPENAI_DEPLOYMENT

    async def complete_json(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[dict[str, Any], TokenUsage]:
        content, usage = await self._chat(
            system=system,
            user=user,
            template_name=template_name,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("llm_json_parse_failed", extra={"template": template_name})
            raise LLMError(f"Agent '{template_name}' returned malformed JSON.") from exc

        if not isinstance(parsed, dict):
            raise LLMError(f"Agent '{template_name}' returned a non-object JSON payload.")
        return parsed, usage

    async def complete_text(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[str, TokenUsage]:
        return await self._chat(system=system, user=user, template_name=template_name)

    async def _chat(
        self,
        *,
        system: str,
        user: str,
        template_name: str,
        response_format: dict[str, str] | None = None,
    ) -> tuple[str, TokenUsage]:
        started = time.perf_counter()
        try:
            completion = await self._invoke_with_retry(system, user, response_format)
        except RetryError as exc:
            logger.error("llm_call_exhausted_retries", extra={"template": template_name})
            raise LLMError(
                f"Azure OpenAI call for '{template_name}' failed after "
                f"{settings.AZURE_OPENAI_MAX_RETRIES} attempts."
            ) from exc

        usage = TokenUsage(
            prompt_tokens=getattr(completion.usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(completion.usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(completion.usage, "total_tokens", 0) or 0,
        )
        logger.info(
            "llm_call_completed",
            extra={
                "template": template_name,
                "deployment": self._deployment,
                "total_tokens": usage.total_tokens,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise LLMError(f"Agent '{template_name}' returned an empty response.")
        return content, usage

    @retry(
        retry=retry_if_exception_type(_RetryableLLMError),
        stop=stop_after_attempt(settings.AZURE_OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=False,
    )
    async def _invoke_with_retry(
        self,
        system: str,
        user: str,
        response_format: dict[str, str] | None,
    ) -> Any:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        kwargs: dict[str, Any] = {
            "model": self._deployment,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": settings.AZURE_OPENAI_TEMPERATURE,
            "max_tokens": settings.AZURE_OPENAI_MAX_TOKENS,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        try:
            if self._token_provider:
                self._client.api_key = self._token_provider()
            return await self._client.chat.completions.create(**kwargs)
        except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
            logger.warning("llm_transient_error", extra={"error": type(exc).__name__})
            raise _RetryableLLMError(str(exc)) from exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                raise _RetryableLLMError(str(exc)) from exc
            raise LLMError(f"Azure OpenAI rejected the request: {exc.message}") from exc
