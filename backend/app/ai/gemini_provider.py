import json
import logging

from app.ai.base import AIProvider, AIProviderError
from app.core.config import settings

logger = logging.getLogger(__name__)

# google.genai's GenerateContentConfig.response_json_schema accepts standard
# JSON Schema (unlike the older, OpenAPI-3.0-subset-only response_schema
# field) but only recognizes this specific keyword subset -- see the
# response_json_schema docstring on google.genai.types.GenerateContentConfig.
# Pydantic's model_json_schema() emits a few keywords outside this list
# (minLength, exclusiveMinimum, default, ...); stripped recursively below
# rather than risking the API rejecting the whole schema over one field.
_SUPPORTED_SCHEMA_KEYS = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required", "propertyOrdering",
}
# Unlike every other key above, `$defs` and `properties` map ARBITRARY names
# (a definition name, a field name) to sub-schemas -- those inner keys must
# never be checked against _SUPPORTED_SCHEMA_KEYS, only recursed into.
_SCHEMA_MAP_KEYS = {"$defs", "properties"}


def _sanitize_schema(node):
    if isinstance(node, dict):
        cleaned = {}
        for key, value in node.items():
            if key not in _SUPPORTED_SCHEMA_KEYS:
                continue
            if key in _SCHEMA_MAP_KEYS and isinstance(value, dict):
                cleaned[key] = {name: _sanitize_schema(sub_schema) for name, sub_schema in value.items()}
            else:
                cleaned[key] = _sanitize_schema(value)
        return cleaned
    if isinstance(node, list):
        return [_sanitize_schema(item) for item in node]
    return node


class GeminiProvider(AIProvider):
    """Structured output via Gemini's native response_json_schema constraint
    (JSON mode + a JSON Schema the model is grammar-constrained to follow) --
    the equivalent of Anthropic's forced-tool-use mechanism for this provider.
    `tool_name` is accepted for interface parity with AnthropicProvider but
    unused: Gemini's structured-output path has no separate "tool" concept.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.gemini_api_key
        self._model = model or settings.gemini_model

    def _client(self):
        if not self._api_key:
            raise AIProviderError(
                "GEMINI_API_KEY is not configured -- set it in the environment to use AI features."
            )
        try:
            from google import genai
        except ImportError as e:
            raise AIProviderError("The 'google-genai' package is not installed.") from e
        return genai.Client(api_key=self._api_key)

    def generate_structured(self, prompt: str, json_schema: dict, tool_name: str) -> dict:
        from google.genai import types

        client = self._client()
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=_sanitize_schema(json_schema),
                ),
            )
        except Exception as e:  # network error, auth error, rate limit, etc.
            logger.error("AI provider generate_structured failed (tool=%s): %s", tool_name, e)
            raise AIProviderError(f"AI provider request failed: {e}") from e

        text = response.text
        if not text:
            logger.error("AI provider returned no content (tool=%s)", tool_name)
            raise AIProviderError("AI provider returned no content.")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("AI provider returned invalid JSON (tool=%s): %s", tool_name, e)
            raise AIProviderError("AI provider returned malformed JSON.") from e

    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        from google.genai import types

        client = self._client()
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_tokens),
            )
        except Exception as e:
            logger.error("AI provider generate_text failed: %s", e)
            raise AIProviderError(f"AI provider request failed: {e}") from e

        if not response.text:
            logger.error("AI provider returned no text content")
            raise AIProviderError("AI provider returned no text content.")
        return response.text
