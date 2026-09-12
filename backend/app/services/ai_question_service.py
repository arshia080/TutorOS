import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError
from app.models.assessment import Assessment, AssessmentStatus, Question, QuestionOption
from app.models.batch import Batch
from app.models.subject import Subject, Topic
from app.models.user import User
from app.schemas.ai import AIGeneratedQuestionSet, GenerateQuestionsRequest
from app.services.ai_validation import AIValidationError, validate_generated_question_set
from app.services.assessment_service import get_owned_assessment

TOOL_NAME = "return_questions"


def _build_generation_prompt(data: GenerateQuestionsRequest, subject_name: str, topic_name: str | None) -> str:
    topic_line = f"Topic: {topic_name}\n" if topic_name else ""
    question_types = ", ".join(t.value for t in data.question_types)
    return (
        "You are an assistant helping a teacher build an exam. Generate exactly "
        f"{data.count} exam questions as a JSON tool call matching the given schema.\n\n"
        f"Grade: {data.grade}\n"
        f"Subject: {subject_name}\n"
        f"{topic_line}"
        f"Difficulty target: {data.difficulty}\n"
        f"Allowed question types: {question_types}\n"
        f"The marks across all {data.count} questions must sum to exactly {data.total_marks}.\n"
        f"The exam's total duration is {data.duration_minutes} minutes -- pace question complexity accordingly.\n\n"
        "Rules:\n"
        "- Every question must be genuinely distinct (no duplicates or near-duplicates).\n"
        "- MCQ: exactly one correct option, at least 2 options total.\n"
        "- MULTI_SELECT: at least one correct option, at least 2 options total.\n"
        "- TRUE_FALSE: exactly two options ('True', 'False'), exactly one correct.\n"
        "- NUMERICAL: exactly one option whose text is the correct numeric answer, marked correct.\n"
        "- SHORT_ANSWER / LONG_ANSWER: no options at all.\n"
        "- Never leave a question with zero marked-correct options for an objective type."
    )


def generate_questions(db: Session, teacher: User, provider: AIProvider, data: GenerateQuestionsRequest) -> Assessment:
    batch = db.get(Batch, data.batch_id)
    if batch is None or batch.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    subject = db.get(Subject, data.subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    topic = None
    if data.topic_id is not None:
        topic = db.get(Topic, data.topic_id)
        if topic is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    prompt = _build_generation_prompt(data, subject.name, topic.name if topic else None)

    try:
        raw = provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), TOOL_NAME)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    try:
        questions = validate_generated_question_set(raw)
    except AIValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": e.errors}) from e

    assessment = Assessment(
        teacher_id=teacher.id,
        batch_id=data.batch_id,
        subject_id=data.subject_id,
        title=f"AI-generated {subject.name} quiz",
        duration_minutes=data.duration_minutes,
        total_marks=data.total_marks,
        status=AssessmentStatus.DRAFT,
    )
    db.add(assessment)
    db.flush()

    for i, q in enumerate(questions):
        question_topic_id = data.topic_id
        if question_topic_id is None and q.topic_name:
            match = db.query(Topic).filter(Topic.subject_id == subject.id, Topic.name.ilike(q.topic_name)).first()
            question_topic_id = match.id if match else None

        question = Question(
            assessment_id=assessment.id,
            question_text=q.question_text,
            question_type=q.question_type,
            topic_id=question_topic_id,
            difficulty=q.difficulty,
            marks=q.marks,
            order_index=i,
            source="AI_GENERATED",
        )
        db.add(question)
        db.flush()
        for j, opt in enumerate(q.options):
            db.add(
                QuestionOption(
                    question_id=question.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=j
                )
            )

    db.commit()
    db.refresh(assessment)
    return assessment


def _build_regeneration_prompt(question: Question, subject_name: str, topic_name: str | None) -> str:
    topic_line = f"Topic: {topic_name}\n" if topic_name else ""
    return (
        "You are helping a teacher replace one exam question they weren't happy with. "
        "Generate exactly ONE new question as a JSON tool call, genuinely different in "
        "wording and content from the original, but covering similar material.\n\n"
        f"Subject: {subject_name}\n"
        f"{topic_line}"
        f"Question type: {question.question_type.value}\n"
        f"Difficulty: {question.difficulty or 'MEDIUM'}\n"
        f"Marks: {question.marks}\n"
        f"Original question being replaced (for context only, do not repeat it): {question.question_text}\n\n"
        "Follow the same option-shape rules as always for this question type."
    )


def regenerate_question(db: Session, teacher: User, provider: AIProvider, assessment_id: uuid.UUID, question_id: uuid.UUID) -> Question:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a published or closed assessment")

    question = db.get(Question, question_id)
    if question is None or question.assessment_id != assessment_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    subject = db.get(Subject, assessment.subject_id)
    topic = db.get(Topic, question.topic_id) if question.topic_id else None

    prompt = _build_regeneration_prompt(question, subject.name, topic.name if topic else None)
    try:
        raw = provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), TOOL_NAME)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    try:
        questions = validate_generated_question_set(raw)
    except AIValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": e.errors}) from e

    new_q = questions[0]
    question.question_text = new_q.question_text
    question.question_type = new_q.question_type
    question.difficulty = new_q.difficulty
    question.marks = new_q.marks
    question.source = "AI_GENERATED"

    db.query(QuestionOption).filter(QuestionOption.question_id == question.id).delete()
    for j, opt in enumerate(new_q.options):
        db.add(QuestionOption(question_id=question.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=j))

    db.commit()
    db.refresh(question)
    return question
