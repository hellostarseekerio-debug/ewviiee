"""Factory that builds the configured AIProvider.

This is the single place that reads `Settings.ai_provider` — everything else
in the codebase depends only on `app.ai.base.AIProvider`.
"""
from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider
from app.core.config import AIProviderName, Settings, get_settings


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()

    if settings.ai_provider == AIProviderName.OPENAI:
        from app.ai.openai_provider import OpenAIProvider

        if not settings.openai_api_key:
            raise ValueError("OAP_OPENAI_API_KEY must be set when ai_provider=openai")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)

    if settings.ai_provider == AIProviderName.ANTHROPIC:
        from app.ai.anthropic_provider import AnthropicProvider

        if not settings.anthropic_api_key:
            raise ValueError("OAP_ANTHROPIC_API_KEY must be set when ai_provider=anthropic")
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    if settings.ai_provider == AIProviderName.AZURE_OPENAI:
        from app.ai.azure_provider import AzureOpenAIProvider

        if not (settings.azure_openai_api_key and settings.azure_openai_endpoint):
            raise ValueError(
                "OAP_AZURE_OPENAI_API_KEY and OAP_AZURE_OPENAI_ENDPOINT must be set "
                "when ai_provider=azure_openai"
            )
        return AzureOpenAIProvider(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment or settings.openai_model,
            api_version=settings.azure_openai_api_version,
        )

    from app.ai.local_provider import LocalLLMProvider

    return LocalLLMProvider(base_url=settings.local_llm_base_url, model=settings.local_llm_model)


@lru_cache
def get_ai_provider() -> AIProvider:
    return build_ai_provider()
