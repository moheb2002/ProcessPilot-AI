"""Shared agent base class."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.prompts.templates import PromptTemplate
from app.schemas.agent import TokenUsage
from app.services.azure_openai import LLMClient

logger = get_logger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[OutputT]):
    """Single-responsibility LLM agent: render prompt -> call model -> validate output."""

    template: PromptTemplate
    output_model: type[OutputT]

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    @abstractmethod
    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        """Map agent inputs onto the prompt template placeholders."""

    async def run(self, **kwargs: Any) -> tuple[OutputT, TokenUsage]:
        system, user = self.template.render(**self.build_context(**kwargs))
        payload, usage = await self._llm.complete_json(
            system=system, user=user, template_name=self.template.name
        )
        try:
            return self.output_model.model_validate(payload), usage
        except PydanticValidationError as exc:
            logger.error(
                "agent_output_validation_failed",
                extra={"agent": self.template.name, "errors": exc.error_count()},
            )
            raise LLMError(
                f"Agent '{self.template.name}' returned a payload that failed validation."
            ) from exc

    @staticmethod
    def serialize(value: Any) -> str:
        """Render nested models as compact JSON for prompt embedding."""
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        elif isinstance(value, list):
            value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
        return json.dumps(value, ensure_ascii=False, indent=2)
