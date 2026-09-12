import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assessment import (
    OBJECTIVE_TYPES,
    SELECTABLE_TYPES,
    Assessment,
    AssessmentAttempt,
    AssessmentStatus,
    AttemptStatus,
    Question,
    QuestionOption,
    QuestionType,
    Response,
    ResponseSelectedOption,
)
from app.models.batch import Batch, BatchStudent, BatchStudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.assessment import AssessmentCreate, AssessmentUpdate, QuestionCreate, ResponseSubmit
from app.services.question_validation import validate_option_shape

ASSESSMENT_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
QUESTION_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
ATTEMPT_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_active_student(db: Session, batch_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    link = db.get(BatchStudent, {"batch_id": batch_id, "student_id": student_id})
    return link is not None and link.status == BatchStudentStatus.ACTIVE


# ---------------------------------------------------------------------------
# Assessment CRUD
# ---------------------------------------------------------------------------


def create_assessment(db: Session, teacher: User, data: AssessmentCreate) -> Assessment:
    batch = db.get(Batch, data.batch_id)
    if batch is None or batch.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if db.get(Subject, data.subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    assessment = Assessment(teacher_id=teacher.id, **data.model_dump())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def get_owned_assessment(db: Session, teacher: User, assessment_id: uuid.UUID) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.teacher_id != teacher.id:
        raise ASSESSMENT_NOT_FOUND
    return assessment


def list_assessments_for_teacher(db: Session, teacher: User) -> list[Assessment]:
    return (
        db.query(Assessment).filter(Assessment.teacher_id == teacher.id).order_by(Assessment.created_at).all()
    )


def list_assessments_for_student(db: Session, student: User) -> list[Assessment]:
    return (
        db.query(Assessment)
        .join(BatchStudent, BatchStudent.batch_id == Assessment.batch_id)
        .filter(
            BatchStudent.student_id == student.id,
            BatchStudent.status == BatchStudentStatus.ACTIVE,
            Assessment.status.in_([AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED]),
        )
        .order_by(Assessment.created_at)
        .all()
    )


def get_assessment_scoped(db: Session, user: User, assessment_id: uuid.UUID) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise ASSESSMENT_NOT_FOUND

    if user.role == UserRole.TEACHER:
        if assessment.teacher_id != user.id:
            raise ASSESSMENT_NOT_FOUND
    elif user.role == UserRole.STUDENT:
        visible = assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED)
        if not visible or not _is_active_student(db, assessment.batch_id, user.id):
            raise ASSESSMENT_NOT_FOUND
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return assessment


def update_assessment(
    db: Session, teacher: User, assessment_id: uuid.UUID, data: AssessmentUpdate
) -> Assessment:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a published or closed assessment"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assessment, field, value)
    db.commit()
    db.refresh(assessment)
    return assessment


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


def add_question(db: Session, teacher: User, assessment_id: uuid.UUID, data: QuestionCreate) -> Question:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot add questions to a published or closed assessment"
        )

    next_index = (
        db.query(func.coalesce(func.max(Question.order_index), -1)).filter(Question.assessment_id == assessment_id).scalar()
    ) + 1

    question = Question(
        assessment_id=assessment_id,
        question_text=data.question_text,
        question_type=data.question_type,
        topic_id=data.topic_id,
        difficulty=data.difficulty,
        marks=data.marks,
        explanation=data.explanation,
        order_index=next_index,
    )
    db.add(question)
    db.flush()

    for i, opt in enumerate(data.options):
        db.add(
            QuestionOption(
                question_id=question.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=i
            )
        )

    db.commit()
    db.refresh(question)
    return question


def update_question(db: Session, teacher: User, assessment_id: uuid.UUID, question_id: uuid.UUID, data) -> Question:
    """Backs the AI Extraction Review actions: Edit / Change topic / Change
    difficulty / Change marks. AI classifications are never immutable (spec
    section 15) -- this is the same edit path regardless of question source.
    """
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a published or closed assessment")

    question = db.get(Question, question_id)
    if question is None or question.assessment_id != assessment_id:
        raise QUESTION_NOT_FOUND

    updates = data.model_dump(exclude_unset=True, exclude={"options"})
    for field, value in updates.items():
        setattr(question, field, value)

    if data.options is not None:
        db.query(QuestionOption).filter(QuestionOption.question_id == question.id).delete()
        for i, opt in enumerate(data.options):
            db.add(
                QuestionOption(question_id=question.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=i)
            )

    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, teacher: User, assessment_id: uuid.UUID, question_id: uuid.UUID) -> None:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status in (AssessmentStatus.PUBLISHED, AssessmentStatus.CLOSED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a published or closed assessment")
    question = db.get(Question, question_id)
    if question is None or question.assessment_id != assessment_id:
        raise QUESTION_NOT_FOUND
    db.delete(question)
    db.commit()


def list_questions(db: Session, assessment_id: uuid.UUID) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.order_index)
        .all()
    )


def get_options_by_question(db: Session, question_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[QuestionOption]]:
    if not question_ids:
        return {}
    options = db.query(QuestionOption).filter(QuestionOption.question_id.in_(question_ids)).order_by(
        QuestionOption.order_index
    ).all()
    result: dict[uuid.UUID, list[QuestionOption]] = {qid: [] for qid in question_ids}
    for opt in options:
        result.setdefault(opt.question_id, []).append(opt)
    return result


# ---------------------------------------------------------------------------
# Publish validation
# ---------------------------------------------------------------------------


def validate_for_publish(db: Session, assessment: Assessment) -> list[str]:
    errors: list[str] = []
    questions = list_questions(db, assessment.id)

    if not questions:
        return ["Assessment must have at least one question"]

    options_by_question = get_options_by_question(db, [q.id for q in questions])
    total_marks = 0.0

    for q in questions:
        total_marks += q.marks
        options = options_by_question.get(q.id, [])
        label = f'Question "{q.question_text[:40]}"'
        option_pairs = [(o.option_text, o.is_correct) for o in options]
        for err in validate_option_shape(q.question_type, option_pairs):
            errors.append(f"{label}: {err}")

    if abs(total_marks - assessment.total_marks) > 1e-9:
        errors.append(
            f"Sum of question marks ({total_marks}) does not match the assessment's declared total_marks ({assessment.total_marks})"
        )

    return errors


def publish_assessment(db: Session, teacher: User, assessment_id: uuid.UUID) -> Assessment:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status not in (AssessmentStatus.DRAFT, AssessmentStatus.REVIEW):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft or in-review assessment can be published")

    errors = validate_for_publish(db, assessment)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors})

    assessment.status = AssessmentStatus.PUBLISHED
    db.commit()
    db.refresh(assessment)
    return assessment


def close_assessment(db: Session, teacher: User, assessment_id: uuid.UUID) -> Assessment:
    assessment = get_owned_assessment(db, teacher, assessment_id)
    if assessment.status != AssessmentStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a published assessment can be closed")
    assessment.status = AssessmentStatus.CLOSED
    db.commit()
    db.refresh(assessment)
    return assessment


# ---------------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------------


def _sum_scores(db: Session, attempt_id: uuid.UUID) -> float:
    total = db.query(func.sum(Response.score)).filter(Response.attempt_id == attempt_id).scalar()
    return float(total or 0.0)


def _finalize(db: Session, attempt, new_status: AttemptStatus, when: datetime) -> None:
    attempt.status = new_status
    attempt.submitted_at = when
    attempt.total_score = _sum_scores(db, attempt.id)
    db.commit()
    db.refresh(attempt)


def _check_and_expire(db: Session, assessment: Assessment, attempt) -> None:
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return
    deadline = _aware(attempt.started_at) + timedelta(minutes=assessment.duration_minutes)
    if _now() > deadline:
        _finalize(db, attempt, AttemptStatus.EXPIRED, deadline)


def start_attempt(db: Session, student: User, assessment_id: uuid.UUID):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.status != AssessmentStatus.PUBLISHED:
        raise ASSESSMENT_NOT_FOUND
    if not _is_active_student(db, assessment.batch_id, student.id):
        raise ASSESSMENT_NOT_FOUND

    existing = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.assessment_id == assessment_id, AssessmentAttempt.student_id == student.id)
        .first()
    )
    if existing is not None:
        _check_and_expire(db, assessment, existing)
        return assessment, existing

    attempt = AssessmentAttempt(assessment_id=assessment_id, student_id=student.id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return assessment, attempt


def get_attempt_scoped(db: Session, user: User, attempt_id: uuid.UUID):
    attempt = db.get(AssessmentAttempt, attempt_id)
    if attempt is None:
        raise ATTEMPT_NOT_FOUND
    assessment = db.get(Assessment, attempt.assessment_id)

    if user.role == UserRole.STUDENT and attempt.student_id != user.id:
        raise ATTEMPT_NOT_FOUND
    if user.role == UserRole.TEACHER and assessment.teacher_id != user.id:
        raise ATTEMPT_NOT_FOUND

    _check_and_expire(db, assessment, attempt)
    return assessment, attempt


def _validate_selected_options(
    question: Question, options: list[QuestionOption], selected_ids: list[uuid.UUID] | None
) -> list[uuid.UUID]:
    selected_ids = selected_ids or []
    valid_ids = {o.id for o in options}
    for oid in selected_ids:
        if oid not in valid_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid option for this question")
    return selected_ids


def _grade_objective(
    question: Question, options: list[QuestionOption], selected_ids: list[uuid.UUID], response_text: str | None
) -> tuple[float, bool]:
    if question.question_type in SELECTABLE_TYPES:
        correct_ids = {o.id for o in options if o.is_correct}
        is_correct = set(selected_ids) == correct_ids
    elif question.question_type == QuestionType.NUMERICAL:
        correct_option = next((o for o in options if o.is_correct), None)
        is_correct = False
        if correct_option is not None and response_text is not None:
            try:
                is_correct = abs(float(response_text) - float(correct_option.option_text)) < 1e-6
            except ValueError:
                is_correct = False
    else:
        raise ValueError(f"{question.question_type} is not an objective type")

    return (question.marks if is_correct else 0.0), is_correct


def submit_response(db: Session, student: User, attempt_id: uuid.UUID, data: ResponseSubmit) -> Response:
    assessment, attempt = get_attempt_scoped(db, student, attempt_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This attempt is no longer in progress")

    question = db.get(Question, data.question_id)
    if question is None or question.assessment_id != assessment.id:
        raise QUESTION_NOT_FOUND

    options = get_options_by_question(db, [question.id]).get(question.id, [])
    selected_ids = _validate_selected_options(question, options, data.selected_option_ids)

    score: float | None = None
    is_correct: bool | None = None
    if question.question_type in OBJECTIVE_TYPES:
        score, is_correct = _grade_objective(question, options, selected_ids, data.response_text)

    response = (
        db.query(Response)
        .filter(Response.attempt_id == attempt_id, Response.question_id == data.question_id)
        .first()
    )
    if response is None:
        response = Response(attempt_id=attempt_id, question_id=data.question_id)
        db.add(response)

    response.response_text = data.response_text
    response.score = score
    response.is_correct = is_correct
    response.time_spent_seconds = data.time_spent_seconds
    response.marked_for_review = data.marked_for_review
    db.flush()

    db.query(ResponseSelectedOption).filter(ResponseSelectedOption.response_id == response.id).delete()
    for oid in selected_ids:
        db.add(ResponseSelectedOption(response_id=response.id, option_id=oid))

    db.commit()
    db.refresh(response)
    return response


def get_selected_option_ids(db: Session, response_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(ResponseSelectedOption.option_id)
        .filter(ResponseSelectedOption.response_id == response_id)
        .all()
    )
    return [r[0] for r in rows]


def list_responses_for_attempt(db: Session, attempt_id: uuid.UUID) -> list[Response]:
    return db.query(Response).filter(Response.attempt_id == attempt_id).all()


def finalize_attempt(db: Session, student: User, attempt_id: uuid.UUID):
    assessment, attempt = get_attempt_scoped(db, student, attempt_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        _finalize(db, attempt, AttemptStatus.SUBMITTED, _now())
    return assessment, attempt


def grade_response(
    db: Session, teacher: User, assessment_id: uuid.UUID, attempt_id: uuid.UUID, question_id: uuid.UUID, score: float
) -> Response:
    assessment = get_owned_assessment(db, teacher, assessment_id)

    attempt = db.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.assessment_id != assessment_id:
        raise ATTEMPT_NOT_FOUND

    question = db.get(Question, question_id)
    if question is None or question.assessment_id != assessment_id:
        raise QUESTION_NOT_FOUND
    if question.question_type in OBJECTIVE_TYPES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Objective questions are graded automatically")
    if score > question.marks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Score cannot exceed the question's {question.marks} marks"
        )

    response = (
        db.query(Response).filter(Response.attempt_id == attempt_id, Response.question_id == question_id).first()
    )
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No response to grade")

    response.score = score
    db.commit()

    attempt.total_score = _sum_scores(db, attempt_id)
    db.commit()
    db.refresh(response)
    return response


def list_attempts_for_assessment(db: Session, teacher: User, assessment_id: uuid.UUID):
    get_owned_assessment(db, teacher, assessment_id)
    return db.query(AssessmentAttempt).filter(AssessmentAttempt.assessment_id == assessment_id).all()
