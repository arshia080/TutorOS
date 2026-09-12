from app.ai.base import AIProvider, AIProviderError
from app.core.config import settings


class AnthropicProvider(AIProvider):
    """Forces structured JSON via Anthropic's tool-use mechanism (a synthetic
    tool whose input_schema is the caller's JSON schema, with tool_choice
    pinned to it) rather than asking nicely in the prompt -- this is what
    "strict structured JSON output" means for Claude models specifically.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.ai_model

    def _client(self):
        if not self._api_key:
            raise AIProviderError(
                "ANTHROPIC_API_KEY is not configured -- set it in the environment to use AI features."
            )
        try:
            import anthropic
        except ImportError as e:
            raise AIProviderError("The 'anthropic' package is not installed.") from e
        return anthropic.Anthropic(api_key=self._api_key)

    def generate_structured(self, prompt: str, json_schema: dict, tool_name: str) -> dict:
        client = self._client()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=4096,
                tools=[{"name": tool_name, "description": "Return the requested data.", "input_schema": json_schema}],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  # network error, auth error, rate limit, etc.
            raise AIProviderError(f"AI provider request failed: {e}") from e

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return block.input

        raise AIProviderError("AI provider did not return the requested structured tool call.")

    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        client = self._client()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AIProviderError(f"AI provider request failed: {e}") from e

        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_blocks:
            raise AIProviderError("AI provider returned no text content.")
        return "\n".join(text_blocks)
