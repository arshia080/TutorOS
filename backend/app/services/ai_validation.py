"""Validates AI-provider output before it ever reaches the database.

Two layers, both mandatory:
1. Pydantic structural validation (AIGeneratedQuestionSet) -- catches missing
   fields, wrong types, invalid question_type/enum values, malformed options.
2. Semantic validation (this module) -- catches things Pydantic can't express:
   duplicate questions, and per-question-type option-shape rules (reusing the
   exact same rules the Phase 3 publish validator enforces, via
   question_validation.validate_option_shape).

Both layers collect every problem before raising, so a teacher (or a test)
sees the whole list at once, not one error at a time.
"""

import pydantic

from app.schemas.ai import AIGeneratedQuestion, AIGeneratedQuestionSet
from app.services.question_validation import validate_option_shape


class AIValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _semantic_errors(questions: list[AIGeneratedQuestion]) -> list[str]:
    errors: list[str] = []

    seen: dict[str, int] = {}
    for q in questions:
        key = q.question_text.strip().lower()
        seen[key] = seen.get(key, 0) + 1
    duplicates = [text for text, count in seen.items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate question(s) detected: {', '.join(duplicates)}")

    for i, q in enumerate(questions):
        label = f'Question {i + 1} ("{q.question_text[:40]}")'
        option_pairs = [(o.option_text, o.is_correct) for o in q.options]
        for err in validate_option_shape(q.question_type, option_pairs):
            errors.append(f"{label}: {err}")

    return errors


def validate_generated_question_set(raw: dict) -> list[AIGeneratedQuestion]:
    """Raises AIValidationError with every problem found; returns the validated
    question list only if it's completely clean.
    """
    try:
        parsed = AIGeneratedQuestionSet.model_validate(raw)
    except pydantic.ValidationError as e:
        errors = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise AIValidationError(errors) from e

    semantic_errors = _semantic_errors(parsed.questions)
    if semantic_errors:
        raise AIValidationError(semantic_errors)

    return parsed.questions
