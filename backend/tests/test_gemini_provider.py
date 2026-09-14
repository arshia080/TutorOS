import pytest

from app.ai.gemini_provider import GeminiProvider, _sanitize_schema
from app.ai.base import AIProviderError


def test_missing_api_key_raises_clear_error_lazily():
    provider = GeminiProvider(api_key=None, model="gemini-2.0-flash")
    with pytest.raises(AIProviderError, match="GEMINI_API_KEY"):
        provider.generate_structured("prompt", {"type": "object"}, "tool")

    with pytest.raises(AIProviderError, match="GEMINI_API_KEY"):
        provider.generate_text("prompt")


def test_constructing_provider_without_key_does_not_raise():
    # Must not blow up at construction/import time -- only when actually invoked.
    GeminiProvider(api_key=None)


def test_sanitize_schema_strips_unsupported_keywords_but_keeps_refs():
    # Mirrors the actual shape Pydantic's model_json_schema() produces --
    # $ref stays untouched (Gemini requires $ref be the *only* key on its
    # object), unsupported sibling keywords (minLength, exclusiveMinimum,
    # default) are dropped, supported ones (type, enum, required, items,
    # properties, $defs) survive.
    raw = {
        "$defs": {
            "Option": {
                "properties": {
                    "text": {"type": "string", "minLength": 1, "title": "Text"},
                    "score": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": ["text", "score"],
                "type": "object",
            }
        },
        "properties": {
            "kind": {"$ref": "#/$defs/QuestionType"},
            "options": {"items": {"$ref": "#/$defs/Option"}, "type": "array", "default": []},
        },
        "required": ["options"],
        "type": "object",
    }

    cleaned = _sanitize_schema(raw)

    assert cleaned["$defs"]["Option"]["properties"]["text"] == {"type": "string", "title": "Text"}
    assert "minLength" not in cleaned["$defs"]["Option"]["properties"]["text"]
    assert "exclusiveMinimum" not in cleaned["$defs"]["Option"]["properties"]["score"]
    assert cleaned["properties"]["kind"] == {"$ref": "#/$defs/QuestionType"}
    assert cleaned["properties"]["options"]["items"] == {"$ref": "#/$defs/Option"}
    assert "default" not in cleaned["properties"]["options"]
    assert cleaned["required"] == ["options"]
