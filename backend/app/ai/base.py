from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when the provider can't produce a usable response (missing API
    key, network failure, the model refusing the forced-tool call, etc.)."""


class AIProvider(ABC):
    """Swappable AI backend. Callers own all validation -- this interface only
    promises "the provider's best attempt at matching json_schema", never a
    guarantee. Every caller must re-validate the returned dict with its own
    Pydantic model before it touches the database (see question_validation.py
    and app/services/ai_question_service.py).
    """

    @abstractmethod
    def generate_structured(self, prompt: str, json_schema: dict, tool_name: str) -> dict:
        """Return a dict shaped by json_schema. Raises AIProviderError on any
        failure to obtain a response at all (not on the response being
        semantically wrong -- that's the caller's job to check)."""

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        """Return a plain-text completion (used for the performance-insight
        narrative, which doesn't need a rigid schema, just a numbers-safe check
        by the caller)."""
