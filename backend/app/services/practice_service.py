"""Personalized practice (product spec section 19).

Weak-topic detection reuses Phase 4's analytics_service.compute_topic_performance
directly -- no separate "weak topic" calculation exists. Practice-set
generation reuses the Phase 5 AI provider + the same two-layer validation gate
question generation uses, restricted to single-answer question types (see
app/models/practice.py for why).

mastery_after is NOT computed by re-running compute_topic_performance() --
practice responses live in their own tables and were never meant to feed the
real exam-based mastery figure shown on dashboards (that would let a student
inflate their "official" mastery by grinding easy practice questions, which
Phase 4's formula was never designed to guard against). Instead, mastery_after
treats the practice set as one new data point using the exact same weighted
formula, weights, and difficulty-weighting as compute_topic_performance:
recent_accuracy becomes the practice set's own accuracy, historical_accuracy
becomes the topic's PREVIOUS recent_accuracy (now the older baseline), and
consistency is recomputed over the practice set's own per-question ratios.
This is a genuinely new number, grounded in the same formula, clearly scoped
to "how did you do on this practice set" -- not a silent rewrite of the
student's real topic mastery. See docs/analytics.md for the full writeup.
"""

import statistics
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError
from app.core.config import settings
from app.models.assessment import QuestionType
from app.models.practice import (
    PRACTICE_QUESTION_TYPES,
    PracticeQuestion,
    PracticeQuestionOption,
    PracticeResponse,
    PracticeSet,
    PracticeSetStatus,
    Recommendation,
    RecommendationStatus,
)
from app.models.subject import Topic
from app.models.user import User
from app.schemas.ai import AIGeneratedQuestionSet
from app.schemas.practice import PracticeResponseSubmit
from app.services.ai_validation import AIValidationError, validate_generated_question_set
from app.services.analytics_service import DIFFICULTY_WEIGHTS, compute_topic_performance

TOOL_NAME = "return_practice_questions"

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Practice set not found")


def _build_practice_prompt(topic_name: str, easy: int, medium: int, hard: int) -> str:
    total = easy + medium + hard
    return (
        "You are generating a personalized practice set for one student who is struggling with a "
        f"specific topic. Generate EXACTLY {total} questions on the topic '{topic_name}', split "
        f"precisely as: {easy} EASY, {medium} MEDIUM, {hard} HARD (set the difficulty field to "
        "exactly one of EASY, MEDIUM, HARD per question, matching this split exactly).\n\n"
        "Only use these question types: MCQ, TRUE_FALSE, NUMERICAL (no multi-select, no "
        "short/long answer -- these must be instantly self-gradable).\n\n"
        "Rules: MCQ needs exactly one correct option and at least 2 options; TRUE_FALSE needs "
        "exactly two options ('True'/'False') with exactly one correct; NUMERICAL needs exactly "
        "one option holding the correct numeric answer, marked correct. Marks: 1 per question. "
        "Every question must be genuinely distinct."
    )


def _validate_difficulty_mix(questions, easy: int, medium: int, hard: int) -> None:
    counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
    for q in questions:
        counts[q.difficulty] = counts.get(q.difficulty, 0) + 1

    errors = []
    if counts.get("EASY", 0) != easy:
        errors.append(f"Expected {easy} EASY questions, got {counts.get('EASY', 0)}")
    if counts.get("MEDIUM", 0) != medium:
        errors.append(f"Expected {medium} MEDIUM questions, got {counts.get('MEDIUM', 0)}")
    if counts.get("HARD", 0) != hard:
        errors.append(f"Expected {hard} HARD questions, got {counts.get('HARD', 0)}")
    for q in questions:
        if q.question_type not in PRACTICE_QUESTION_TYPES:
            errors.append(f'Question "{q.question_text[:40]}": {q.question_type.value} is not allowed in a practice set')

    if errors:
        raise AIValidationError(errors)


def generate_practice_set(
    db: Session,
    student: User,
    provider: AIProvider,
    topic_id: uuid.UUID,
    easy: int | None,
    medium: int | None,
    hard: int | None,
) -> PracticeSet:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    perf = compute_topic_performance(db, student.id, topic_id)
    if perf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No performance data for this topic yet")

    easy = settings.practice_set_easy_count if easy is None else easy
    medium = settings.practice_set_medium_count if medium is None else medium
    hard = settings.practice_set_hard_count if hard is None else hard
    if easy + medium + hard == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Practice set must have at least one question")

    prompt = _build_practice_prompt(topic.name, easy, medium, hard)
    try:
        raw = provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), TOOL_NAME)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    try:
        questions = validate_generated_question_set(raw)
        _validate_difficulty_mix(questions, easy, medium, hard)
    except AIValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": e.errors}) from e

    practice_set = PracticeSet(
        student_id=student.id,
        topic_id=topic_id,
        title=f"{topic.name} practice",
        difficulty="MIXED",
        mastery_before=perf.mastery_score,
    )
    db.add(practice_set)
    db.flush()

    for i, q in enumerate(questions):
        pq = PracticeQuestion(
            practice_set_id=practice_set.id,
            question_text=q.question_text,
            question_type=q.question_type,
            difficulty=q.difficulty,
            marks=q.marks,
            order_index=i,
        )
        db.add(pq)
        db.flush()
        for j, opt in enumerate(q.options):
            db.add(
                PracticeQuestionOption(
                    practice_question_id=pq.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=j
                )
            )

    gap = round(settings.weak_topic_mastery_threshold - perf.mastery_score)
    db.add(
        Recommendation(
            student_id=student.id,
            topic_id=topic_id,
            type="PRACTICE_SET",
            recommendation_text=f"Practice set generated for {topic.name} ({perf.mastery_score}% mastery).",
            priority=max(0, gap),
            status=RecommendationStatus.PENDING,
            practice_set_id=practice_set.id,
        )
    )

    db.commit()
    db.refresh(practice_set)
    return practice_set


def get_owned_practice_set(db: Session, student: User, practice_set_id: uuid.UUID) -> PracticeSet:
    ps = db.get(PracticeSet, practice_set_id)
    if ps is None or ps.student_id != student.id:
        raise NOT_FOUND
    return ps


def list_practice_questions(db: Session, practice_set_id: uuid.UUID) -> list[PracticeQuestion]:
    return (
        db.query(PracticeQuestion)
        .filter(PracticeQuestion.practice_set_id == practice_set_id)
        .order_by(PracticeQuestion.order_index)
        .all()
    )


def list_practice_options(db: Session, question_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[PracticeQuestionOption]]:
    if not question_ids:
        return {}
    options = (
        db.query(PracticeQuestionOption)
        .filter(PracticeQuestionOption.practice_question_id.in_(question_ids))
        .order_by(PracticeQuestionOption.order_index)
        .all()
    )
    result: dict[uuid.UUID, list[PracticeQuestionOption]] = {qid: [] for qid in question_ids}
    for opt in options:
        result.setdefault(opt.practice_question_id, []).append(opt)
    return result


def submit_practice_response(db: Session, student: User, practice_set_id: uuid.UUID, data: PracticeResponseSubmit) -> PracticeResponse:
    practice_set = get_owned_practice_set(db, student, practice_set_id)
    if practice_set.status != PracticeSetStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This practice set is already completed")

    question = db.get(PracticeQuestion, data.question_id)
    if question is None or question.practice_set_id != practice_set_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    options = list_practice_options(db, [question.id]).get(question.id, [])
    is_correct = False

    if question.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
        if data.selected_option_id is not None:
            valid_ids = {o.id for o in options}
            if data.selected_option_id not in valid_ids:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid option for this question")
            selected = next(o for o in options if o.id == data.selected_option_id)
            is_correct = selected.is_correct
    elif question.question_type == QuestionType.NUMERICAL:
        correct_option = next((o for o in options if o.is_correct), None)
        if correct_option is not None and data.response_text is not None:
            try:
                is_correct = abs(float(data.response_text) - float(correct_option.option_text)) < 1e-6
            except ValueError:
                is_correct = False

    score = question.marks if is_correct else 0.0

    response = (
        db.query(PracticeResponse)
        .filter(PracticeResponse.practice_set_id == practice_set_id, PracticeResponse.practice_question_id == question.id)
        .first()
    )
    if response is None:
        response = PracticeResponse(practice_set_id=practice_set_id, practice_question_id=question.id, is_correct=False, score=0.0)
        db.add(response)

    response.selected_option_id = data.selected_option_id
    response.response_text = data.response_text
    response.is_correct = is_correct
    response.score = score
    db.commit()
    db.refresh(response)
    return response


def complete_practice_set(db: Session, student: User, practice_set_id: uuid.UUID) -> tuple[PracticeSet, list[PracticeResponse]]:
    practice_set = get_owned_practice_set(db, student, practice_set_id)
    if practice_set.status == PracticeSetStatus.COMPLETED:
        responses = db.query(PracticeResponse).filter(PracticeResponse.practice_set_id == practice_set_id).all()
        return practice_set, responses

    questions = list_practice_questions(db, practice_set_id)
    responses = db.query(PracticeResponse).filter(PracticeResponse.practice_set_id == practice_set_id).all()
    if not responses:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Answer at least one question before completing")

    marks_by_question = {q.id: q.marks for q in questions}
    difficulty_by_question = {q.id: q.difficulty for q in questions}

    total_score = sum(r.score for r in responses)
    total_marks = sum(marks_by_question[r.practice_question_id] for r in responses)
    practice_accuracy = total_score / total_marks if total_marks else 0.0

    weighted_score = 0.0
    weighted_marks = 0.0
    for r in responses:
        w = DIFFICULTY_WEIGHTS.get(difficulty_by_question.get(r.practice_question_id, "EASY"), 1.0)
        weighted_score += r.score * w
        weighted_marks += marks_by_question[r.practice_question_id] * w
    difficulty_adjusted = weighted_score / weighted_marks if weighted_marks else 0.0

    ratios = [r.score / marks_by_question[r.practice_question_id] for r in responses if marks_by_question[r.practice_question_id]]
    consistency = max(0.0, 1.0 - 2 * statistics.pstdev(ratios)) * 100 if ratios else 100.0

    before_perf = compute_topic_performance(db, student.id, practice_set.topic_id)
    historical = before_perf.recent_accuracy / 100 if before_perf else practice_set.mastery_before / 100

    mastery_after = 100 * (
        settings.mastery_weight_recent * practice_accuracy
        + settings.mastery_weight_historical * historical
        + settings.mastery_weight_difficulty_adjusted * difficulty_adjusted
        + settings.mastery_weight_consistency * (consistency / 100)
    )
    mastery_after = max(0.0, min(100.0, round(mastery_after, 2)))

    practice_set.status = PracticeSetStatus.COMPLETED
    practice_set.mastery_after = mastery_after
    practice_set.completed_at = datetime.now(timezone.utc)

    recommendation = db.query(Recommendation).filter(Recommendation.practice_set_id == practice_set_id).first()
    if recommendation is not None:
        recommendation.status = RecommendationStatus.COMPLETED

    db.commit()
    db.refresh(practice_set)
    return practice_set, responses
