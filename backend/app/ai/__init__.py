from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider, AIProviderError
from app.ai.gemini_provider import GeminiProvider
from app.core.config import settings

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """FastAPI dependency / call-site seam. Tests override this (via
    app.dependency_overrides or by monkeypatching this function) to inject a
    fake provider -- no real API calls happen in the test suite.

    Which concrete provider gets built is controlled by settings.ai_provider
    ("anthropic" or "gemini") -- swapping providers is a one-line env var
    change, never a code change at any call site.
    """
    global _provider
    if _provider is None:
        if settings.ai_provider == "gemini":
            _provider = GeminiProvider()
        else:
            _provider = AnthropicProvider()
    return _provider


__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]
