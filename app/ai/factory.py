"""Factory that builds the configured AIProvider.

This is the single place that reads `Settings.ai_provider` — everything else
in the codebase depends only on `app.ai.base.AIProvider`.

Privacy: `OPENAI`, `ANTHROPIC` and `AZURE_OPENAI` are "cloud" providers -
using them sends document text to a third party. `LOCAL` is the only
provider that keeps everything on-premises. Callers that need to respect the
office's cloud-AI policy should use `get_guarded_ai_provider()` instead of
`get_ai_provider()` / `build_ai_provider()` directly.
"""
from __future__ import annotations

import time
from functools import lru_cache

from app.ai.base import AIProvider, AIResponse
from app.core.config import AIProviderName, Settings, get_settings
from app.core.logging_config import get_logger

logger = get_logger("ai.factory")

CLOUD_PROVIDERS = {AIProviderName.OPENAI, AIProviderName.ANTHROPIC, AIProviderName.AZURE_OPENAI}


def is_cloud_provider(provider_name: AIProviderName) -> bool:
    return provider_name in CLOUD_PROVIDERS


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


class AIUsagePolicyError(Exception):
    """Raised when the configured provider is a cloud provider that the
    office administrator has not explicitly enabled."""


class LoggingAIProvider:
    """Wraps an AIProvider so every call is recorded to `ai_usage_logs`
    (metadata only - provider/operation/timing/success, never document
    content or the prompt itself) without every call site needing to
    remember to log it."""

    def __init__(self, inner: AIProvider, is_cloud: bool) -> None:
        self._inner = inner
        self._is_cloud = is_cloud
        self.name = inner.name

    def _record(self, operation: str, start: float, success: bool) -> None:
        from app.core.database import session_scope
        from app.core.models import AIUsageLog

        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            with session_scope() as session:
                session.add(
                    AIUsageLog(
                        provider=self.name,
                        operation=operation,
                        is_cloud_provider=self._is_cloud,
                        success=success,
                        duration_ms=duration_ms,
                    )
                )
        except Exception as exc:  # pragma: no cover - defensive, must never break AI calls
            logger.error("ai_usage_log_failed", error=str(exc))
        logger.info(
            "ai_call", provider=self.name, operation=operation, cloud=self._is_cloud, success=success
        )

    def classify(self, text: str, categories: list[str], context: str = "") -> AIResponse:
        start = time.perf_counter()
        try:
            result = self._inner.classify(text, categories, context)
            self._record("classify", start, True)
            return result
        except Exception:
            self._record("classify", start, False)
            raise

    def extract_fields(self, text: str, schema: dict[str, str], context: str = "") -> AIResponse:
        start = time.perf_counter()
        try:
            result = self._inner.extract_fields(text, schema, context)
            self._record("extract_fields", start, True)
            return result
        except Exception:
            self._record("extract_fields", start, False)
            raise

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        start = time.perf_counter()
        try:
            result = self._inner.complete(prompt, system)
            self._record("complete", start, True)
            return result
        except Exception:
            self._record("complete", start, False)
            raise


def get_guarded_ai_provider(settings: Settings | None = None) -> AIProvider | None:
    """Builds the configured AI provider, but refuses to instantiate a cloud
    provider unless the admin has explicitly enabled `allow_cloud_ai` via the
    system settings table. Returns None (not an exception) when AI assistance
    is unavailable, since the rule engine must always work standalone -
    AI is a fallback, never a dependency.
    """
    settings = settings or get_settings()
    cloud = is_cloud_provider(settings.ai_provider)

    if cloud:
        from app.core.database import session_scope
        from app.core.system_settings import ALLOW_CLOUD_AI, get_bool_setting

        try:
            with session_scope() as session:
                allowed = get_bool_setting(session, ALLOW_CLOUD_AI)
        except Exception as exc:
            logger.warning("cloud_ai_policy_check_failed", error=str(exc))
            allowed = False

        if not allowed:
            logger.warning(
                "cloud_ai_blocked",
                provider=settings.ai_provider.value,
                reason="allow_cloud_ai is disabled - enable it in Settings to use a cloud AI provider",
            )
            return None

    try:
        provider = build_ai_provider(settings)
    except Exception as exc:
        logger.warning("ai_provider_unavailable", error=str(exc))
        return None

    return LoggingAIProvider(provider, is_cloud=cloud)
