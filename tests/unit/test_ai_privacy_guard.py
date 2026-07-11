"""Verifies the privacy-critical behavior: cloud AI providers must never be
used unless an administrator has explicitly enabled them via system
settings, and the default is local/private."""
from __future__ import annotations

from app.ai.factory import get_guarded_ai_provider, is_cloud_provider
from app.ai.local_provider import LocalLLMProvider
from app.core.config import AIProviderName, Settings
from app.core.database import init_db, session_scope
from app.core.system_settings import ALLOW_CLOUD_AI, set_setting


def test_local_provider_is_not_cloud():
    assert not is_cloud_provider(AIProviderName.LOCAL)


def test_openai_anthropic_azure_are_cloud_providers():
    assert is_cloud_provider(AIProviderName.OPENAI)
    assert is_cloud_provider(AIProviderName.ANTHROPIC)
    assert is_cloud_provider(AIProviderName.AZURE_OPENAI)


def test_local_provider_always_available_without_admin_opt_in():
    init_db()
    settings = Settings(ai_provider=AIProviderName.LOCAL)
    provider = get_guarded_ai_provider(settings)
    assert provider is not None
    assert isinstance(provider._inner if hasattr(provider, "_inner") else provider, LocalLLMProvider)


def test_cloud_provider_blocked_by_default(monkeypatch):
    init_db()
    settings = Settings(ai_provider=AIProviderName.OPENAI, openai_api_key="sk-fake")
    provider = get_guarded_ai_provider(settings)
    assert provider is None  # default allow_cloud_ai=false blocks it


def test_cloud_provider_allowed_after_explicit_admin_opt_in():
    init_db()
    with session_scope() as session:
        set_setting(session, ALLOW_CLOUD_AI, "true", updated_by="admin")

    settings = Settings(ai_provider=AIProviderName.OPENAI, openai_api_key="sk-fake")
    provider = get_guarded_ai_provider(settings)
    assert provider is not None
