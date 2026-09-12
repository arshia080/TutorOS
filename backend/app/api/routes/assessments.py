import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.assessment import AssessmentStatus, AttemptStatus, Question
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentRead,
    AssessmentUpdate,
    AttemptRead,
    AttemptReview,
    GradeRequest,
    QuestionCreate,
    QuestionOptionRead,
    QuestionRead,
    ResponseGradedRead,
    ResponseRead,
    ResponseSubmit,
    StartAttemptResponse,
)
from app.services import analytics_service
from app.services import assessment_service as svc

router = APIRouter(tags=["assessments"])
require_teacher = require_role(UserRole.TEACHER)
require_student = require_role(UserRole.STUDENT)


def _question_read(db: Session, question, include_correct: bool) -> QuestionRead:
    options = svc.get_options_by_question(db, [question.id]).get(question.id, [])
    option_reads = [
        QuestionOptionRead(
            id=o.id, option_text=o.option_text, order_index=o.order_index, is_correct=o.is_correct if include_correct else None
        )
        for o in options
    ]
    read = QuestionRead.model_validate(question)
    read.options = option_reads
    return read


@router.post("/assessments", response_model=AssessmentRead, status_code=201)
def create_assessment(
    data: AssessmentCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> AssessmentRead:
    return svc.create_assessment(db, teacher, data)


@router.get("/assessments", response_model=list[AssessmentRead])
def list_assessments(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[AssessmentRead]:
    if current_user.role == UserRole.TEACHER:
        return svc.list_assessments_for_teacher(db, current_user)
    if current_user.role == UserRole.STUDENT:
        return svc.list_assessments_for_student(db, current_user)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("/assessments/{assessment_id}", response_model=AssessmentRead)
def get_assessment(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> AssessmentRead:
    return svc.get_assessment_scoped(db, current_user, assessment_id)


@router.patch("/assessments/{assessment_id}", response_model=AssessmentRead)
def update_assessment(
    assessment_id: uuid.UUID,
    data: AssessmentUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> AssessmentRead:
    return svc.update_assessment(db, teacher, assessment_id, data)


@router.post("/assessments/{assessment_id}/questions", response_model=QuestionRead, status_code=201)
def add_question(
    assessment_id: uuid.UUID,
    data: QuestionCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuestionRead:
    question = svc.add_question(db, teacher, assessment_id, data)
    return _question_read(db, question, include_correct=True)


@router.get("/assessments/{assessment_id}/questions", response_model=list[QuestionRead])
def list_questions(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[QuestionRead]:
    svc.get_owned_assessment(db, teacher, assessment_id)
    questions = svc.list_questions(db, assessment_id)
    return [_question_read(db, q, include_correct=True) for q in questions]


@router.delete("/assessments/{assessment_id}/questions/{question_id}", status_code=204)
def delete_question(
    assessment_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> None:
    svc.delete_question(db, teacher, assessment_id, question_id)


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentRead)
def publish_assessment(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> AssessmentRead:
    return svc.publish_assessment(db, teacher, assessment_id)


@router.post("/assessments/{assessment_id}/close", response_model=AssessmentRead)
def close_assessment(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> AssessmentRead:
    return svc.close_assessment(db, teacher, assessment_id)


@router.post("/assessments/{assessment_id}/attempts", response_model=StartAttemptResponse, status_code=201)
def start_attempt(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), student: User = Depends(require_student)
) -> StartAttemptResponse:
    assessment, attempt = svc.start_attempt(db, student, assessment_id)
    questions = svc.list_questions(db, assessment_id)
    deadline = attempt.started_at + timedelta(minutes=assessment.duration_minutes)
    return StartAttemptResponse(
        id=attempt.id,
        assessment_id=assessment_id,
        status=attempt.status,
        started_at=attempt.started_at,
        duration_minutes=assessment.duration_minutes,
        deadline=deadline,
        questions=[_question_read(db, q, include_correct=False) for q in questions],
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptRead)
def get_attempt(
    attempt_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> AttemptRead:
    _assessment, attempt = svc.get_attempt_scoped(db, current_user, attempt_id)
    return attempt


@router.get("/attempts/{attempt_id}/responses", response_model=list[ResponseRead])
def list_my_responses(
    attempt_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[ResponseRead]:
    svc.get_attempt_scoped(db, current_user, attempt_id)
    responses = svc.list_responses_for_attempt(db, attempt_id)
    return [
        ResponseRead(
            question_id=r.question_id,
            selected_option_ids=svc.get_selected_option_ids(db, r.id),
            response_text=r.response_text,
            marked_for_review=r.marked_for_review,
        )
        for r in responses
    ]


@router.post("/attempts/{attempt_id}/responses", response_model=ResponseRead)
def submit_response(
    attempt_id: uuid.UUID,
    data: ResponseSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> ResponseRead:
    response = svc.submit_response(db, student, attempt_id, data)
    return ResponseRead(
        question_id=response.question_id,
        selected_option_ids=svc.get_selected_option_ids(db, response.id),
        response_text=response.response_text,
        marked_for_review=response.marked_for_review,
    )


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptRead)
def submit_attempt(
    attempt_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> AttemptRead:
    assessment, attempt = svc.finalize_attempt(db, student, attempt_id)
    topic_ids = analytics_service.topics_touched_by_assessment(db, assessment.id)
    if topic_ids:
        background_tasks.add_task(analytics_service.recalculate_after_attempt, student.id, topic_ids)
    return attempt


@router.get("/attempts/{attempt_id}/review", response_model=AttemptReview)
def review_attempt(
    attempt_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> AttemptReview:
    assessment, attempt = svc.get_attempt_scoped(db, current_user, attempt_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Results are available once the attempt is submitted"
        )

    questions = svc.list_questions(db, assessment.id)
    responses = svc.list_responses_for_attempt(db, attempt_id)

    return AttemptReview(
        attempt=attempt,
        questions=[_question_read(db, q, include_correct=True) for q in questions],
        responses=[
            ResponseGradedRead(
                id=r.id,
                question_id=r.question_id,
                response_text=r.response_text,
                score=r.score,
                is_correct=r.is_correct,
                selected_option_ids=svc.get_selected_option_ids(db, r.id),
            )
            for r in responses
        ],
    )


@router.get("/assessments/{assessment_id}/attempts", response_model=list[AttemptRead])
def list_attempts(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[AttemptRead]:
    return svc.list_attempts_for_assessment(db, teacher, assessment_id)


@router.patch(
    "/assessments/{assessment_id}/attempts/{attempt_id}/responses/{question_id}/grade",
    response_model=ResponseRead,
)
def grade_response(
    assessment_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    data: GradeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> ResponseRead:
    response = svc.grade_response(db, teacher, assessment_id, attempt_id, question_id, data.score)
    _assessment, attempt = svc.get_attempt_scoped(db, teacher, attempt_id)
    question = db.get(Question, question_id)
    if question is not None and question.topic_id is not None:
        background_tasks.add_task(analytics_service.recalculate_after_attempt, attempt.student_id, [question.topic_id])
    return ResponseRead(
        question_id=response.question_id,
        selected_option_ids=[],
        response_text=response.response_text,
        marked_for_review=response.marked_for_review,
    )
