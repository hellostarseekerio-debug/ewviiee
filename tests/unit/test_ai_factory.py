from __future__ import annotations

import pytest

from app.ai.factory import build_ai_provider
from app.ai.local_provider import LocalLLMProvider
from app.core.config import AIProviderName, Settings


def test_factory_builds_local_provider_by_default():
    settings = Settings(ai_provider=AIProviderName.LOCAL)
    provider = build_ai_provider(settings)
    assert isinstance(provider, LocalLLMProvider)
    assert provider.name == "local"


def test_factory_raises_when_openai_key_missing():
    settings = Settings(ai_provider=AIProviderName.OPENAI, openai_api_key=None)
    with pytest.raises(ValueError):
        build_ai_provider(settings)


def test_factory_raises_when_anthropic_key_missing():
    settings = Settings(ai_provider=AIProviderName.ANTHROPIC, anthropic_api_key=None)
    with pytest.raises(ValueError):
        build_ai_provider(settings)


def test_factory_raises_when_azure_config_missing():
    settings = Settings(ai_provider=AIProviderName.AZURE_OPENAI)
    with pytest.raises(ValueError):
        build_ai_provider(settings)
