import pytest

from app.services.ai_validation import AIValidationError, validate_generated_question_set


def _mcq(text="What is 2+2?", correct_count=1, marks=2):
    options = [{"option_text": "3", "is_correct": False}, {"option_text": "4", "is_correct": correct_count >= 1}]
    if correct_count == 2:
        options[0]["is_correct"] = True
    return {"question_text": text, "question_type": "MCQ", "difficulty": "EASY", "marks": marks, "options": options}


def test_valid_question_set_passes():
    data = {"questions": [_mcq()]}
    questions = validate_generated_question_set(data)
    assert len(questions) == 1
    assert questions[0].difficulty == "EASY"


def test_missing_required_field_rejected():
    data = {"questions": [{"question_type": "MCQ", "difficulty": "EASY", "marks": 2, "options": []}]}
    with pytest.raises(AIValidationError) as exc:
        validate_generated_question_set(data)
    assert any("question_text" in e for e in exc.value.errors)


def test_invalid_question_type_rejected():
    data = {"questions": [{**_mcq(), "question_type": "ESSAY"}]}
    with pytest.raises(AIValidationError):
        validate_generated_question_set(data)


def test_invalid_marks_rejected():
    data = {"questions": [{**_mcq(), "marks": -1}]}
    with pytest.raises(AIValidationError):
        validate_generated_question_set(data)

    data_zero = {"questions": [{**_mcq(), "marks": 0}]}
    with pytest.raises(AIValidationError):
        validate_generated_question_set(data_zero)


def test_malformed_options_rejected():
    # option missing "is_correct"
    data = {
        "questions": [
            {
                "question_text": "Pick one",
                "question_type": "MCQ",
                "difficulty": "EASY",
                "marks": 2,
                "options": [{"option_text": "A"}, {"option_text": "B", "is_correct": True}],
            }
        ]
    }
    with pytest.raises(AIValidationError):
        validate_generated_question_set(data)


def test_missing_correct_answer_rejected():
    data = {"questions": [_mcq(correct_count=0)]}
    with pytest.raises(AIValidationError) as exc:
        validate_generated_question_set(data)
    assert any("exactly one correct option" in e for e in exc.value.errors)


def test_mcq_with_two_correct_answers_rejected():
    data = {"questions": [_mcq(correct_count=2)]}
    with pytest.raises(AIValidationError):
        validate_generated_question_set(data)


def test_duplicate_questions_rejected():
    data = {"questions": [_mcq(text="What is 2+2?"), _mcq(text="what is 2+2? ")]}
    with pytest.raises(AIValidationError) as exc:
        validate_generated_question_set(data)
    assert any("Duplicate question" in e for e in exc.value.errors)


def test_subjective_question_with_options_rejected():
    data = {
        "questions": [
            {
                "question_text": "Explain photosynthesis",
                "question_type": "SHORT_ANSWER",
                "difficulty": "MEDIUM",
                "marks": 5,
                "options": [{"option_text": "should not be here", "is_correct": True}],
            }
        ]
    }
    with pytest.raises(AIValidationError) as exc:
        validate_generated_question_set(data)
    assert any("must not have options" in e for e in exc.value.errors)


def test_true_false_and_numerical_and_subjective_valid():
    data = {
        "questions": [
            {
                "question_text": "The earth is round.",
                "question_type": "TRUE_FALSE",
                "difficulty": "EASY",
                "marks": 1,
                "options": [{"option_text": "True", "is_correct": True}, {"option_text": "False", "is_correct": False}],
            },
            {
                "question_text": "What is the value of pi to the nearest integer?",
                "question_type": "NUMERICAL",
                "difficulty": "MEDIUM",
                "marks": 2,
                "options": [{"option_text": "3", "is_correct": True}],
            },
            {
                "question_text": "Explain Newton's second law.",
                "question_type": "LONG_ANSWER",
                "difficulty": "HARD",
                "marks": 5,
                "options": [],
            },
        ]
    }
    questions = validate_generated_question_set(data)
    assert len(questions) == 3


def test_empty_question_list_rejected():
    with pytest.raises(AIValidationError):
        validate_generated_question_set({"questions": []})


def test_collects_multiple_errors_at_once():
    data = {"questions": [_mcq(correct_count=0), _mcq(correct_count=0)]}
    # Both questions have identical text AND both are missing a correct answer --
    # should report both the duplicate and both missing-correct-answer problems.
    with pytest.raises(AIValidationError) as exc:
        validate_generated_question_set(data)
    assert len(exc.value.errors) >= 2
