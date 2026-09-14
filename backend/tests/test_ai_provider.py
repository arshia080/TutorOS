import pytest

import app.ai as ai_module
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProviderError
from app.ai.gemini_provider import GeminiProvider
from app.core.config import settings


def test_missing_api_key_raises_clear_error_lazily():
    provider = AnthropicProvider(api_key=None, model="claude-sonnet-5")
    with pytest.raises(AIProviderError, match="ANTHROPIC_API_KEY"):
        provider.generate_structured("prompt", {"type": "object"}, "tool")

    with pytest.raises(AIProviderError, match="ANTHROPIC_API_KEY"):
        provider.generate_text("prompt")


def test_constructing_provider_without_key_does_not_raise():
    # Must not blow up at construction/import time -- only when actually invoked.
    AnthropicProvider(api_key=None)


def test_get_ai_provider_selects_by_settings(monkeypatch):
    monkeypatch.setattr(ai_module, "_provider", None)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    assert isinstance(ai_module.get_ai_provider(), GeminiProvider)

    monkeypatch.setattr(ai_module, "_provider", None)
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    assert isinstance(ai_module.get_ai_provider(), AnthropicProvider)
