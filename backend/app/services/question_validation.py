"""Question option-shape rules, shared between the Phase 3 publish validator
(app/services/assessment_service.py) and the AI question validators (Phase 5) --
one place defines what a "valid MCQ" etc. looks like, so both paths agree.
"""

from app.models.assessment import QuestionType


def validate_option_shape(question_type: QuestionType, options: list[tuple[str, bool]]) -> list[str]:
    """options: list of (option_text, is_correct). Returns error strings with no
    question-specific prefix -- callers prepend their own question label.
    """
    errors: list[str] = []
    correct = [o for o in options if o[1]]

    if question_type == QuestionType.MCQ:
        if len(options) < 2:
            errors.append("MCQ must have at least 2 options")
        if len(correct) != 1:
            errors.append("MCQ must have exactly one correct option")
    elif question_type == QuestionType.MULTI_SELECT:
        if len(options) < 2:
            errors.append("multi-select must have at least 2 options")
        if len(correct) == 0:
            errors.append("multi-select must have at least one correct option")
    elif question_type == QuestionType.TRUE_FALSE:
        if len(options) != 2:
            errors.append("true/false must have exactly 2 options")
        if len(correct) != 1:
            errors.append("true/false must have exactly one correct option")
    elif question_type == QuestionType.NUMERICAL:
        if len(options) != 1:
            errors.append("numerical questions must store exactly one correct answer")
        elif not correct:
            errors.append("numerical answer must be marked correct")
        else:
            try:
                float(options[0][0])
            except ValueError:
                errors.append("numerical answer must be a valid number")
    elif question_type in (QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER):
        if options:
            errors.append("subjective questions must not have options")

    return errors
