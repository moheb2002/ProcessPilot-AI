"""Azure OpenAI client authentication wiring."""

from unittest.mock import Mock

from app.core.config import settings
from app.services.azure_openai import (
    AzureOpenAIClient,
    _foundry_inference_endpoint,
    _token_scope,
)


def test_token_scope_matches_endpoint_type() -> None:
    assert (
        _token_scope("https://example.services.ai.azure.com/api/projects/demo")
        == "https://ai.azure.com/.default"
    )
    assert (
        _token_scope("https://example.openai.azure.com")
        == "https://cognitiveservices.azure.com/.default"
    )
    assert (
        _foundry_inference_endpoint(
            "https://example.services.ai.azure.com/api/projects/demo"
        )
        == "https://example.services.ai.azure.com/openai/v1/"
    )


def test_client_uses_azure_cli_token_provider(monkeypatch) -> None:
    credential = Mock()
    token_provider = Mock()
    client_factory = Mock()

    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr("azure.identity.AzureCliCredential", Mock(return_value=credential))
    provider_factory = Mock(return_value=token_provider)
    monkeypatch.setattr("azure.identity.get_bearer_token_provider", provider_factory)
    monkeypatch.setattr("openai.AsyncAzureOpenAI", client_factory)

    AzureOpenAIClient()

    provider_factory.assert_called_once_with(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    assert client_factory.call_args.kwargs["azure_ad_token_provider"] is token_provider
    assert "api_key" not in client_factory.call_args.kwargs


def test_foundry_client_uses_versionless_inference_endpoint(monkeypatch) -> None:
    token_provider = Mock(return_value="token")
    client_factory = Mock()

    monkeypatch.setattr(
        settings,
        "AZURE_OPENAI_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setattr("azure.identity.AzureCliCredential", Mock())
    monkeypatch.setattr(
        "azure.identity.get_bearer_token_provider",
        Mock(return_value=token_provider),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", client_factory)

    AzureOpenAIClient()

    assert client_factory.call_args.kwargs["base_url"].endswith("/openai/v1/")
    assert client_factory.call_args.kwargs["api_key"] == "token"
    assert "api_version" not in client_factory.call_args.kwargs