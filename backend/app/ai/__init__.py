from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider, AIProviderError

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """FastAPI dependency / call-site seam. Tests override this (via
    app.dependency_overrides or by monkeypatching this function) to inject a
    fake provider -- no real API calls happen in the test suite.
    """
    global _provider
    if _provider is None:
        _provider = AnthropicProvider()
    return _provider


__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]
