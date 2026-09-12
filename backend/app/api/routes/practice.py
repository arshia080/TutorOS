import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.api.routes.ai import get_provider
from app.core.deps import require_role
from app.db.session import get_db
from app.models.practice import PracticeSetStatus
from app.models.subject import Topic
from app.models.user import User, UserRole
from app.schemas.practice import (
    GeneratePracticeRequest,
    PracticeCompletionRead,
    PracticeOptionRead,
    PracticeQuestionRead,
    PracticeResponseGradedRead,
    PracticeResponseRead,
    PracticeResponseSubmit,
    PracticeSetRead,
)
from app.services import practice_service

router = APIRouter(tags=["practice"])
require_student = require_role(UserRole.STUDENT)


def _question_read(db: Session, question, include_correct: bool) -> PracticeQuestionRead:
    options = practice_service.list_practice_options(db, [question.id]).get(question.id, [])
    return PracticeQuestionRead(
        id=question.id,
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty=question.difficulty,
        marks=question.marks,
        order_index=question.order_index,
        options=[
            PracticeOptionRead(id=o.id, option_text=o.option_text, is_correct=o.is_correct if include_correct else None)
            for o in options
        ],
    )


def _set_read(db: Session, ps) -> PracticeSetRead:
    topic = db.get(Topic, ps.topic_id)
    include_correct = ps.status == PracticeSetStatus.COMPLETED
    questions = practice_service.list_practice_questions(db, ps.id)
    return PracticeSetRead(
        id=ps.id,
        topic_id=ps.topic_id,
        topic_name=topic.name if topic else "",
        title=ps.title,
        difficulty=ps.difficulty,
        status=ps.status,
        mastery_before=ps.mastery_before,
        mastery_after=ps.mastery_after,
        created_at=ps.created_at,
        completed_at=ps.completed_at,
        questions=[_question_read(db, q, include_correct) for q in questions],
    )


@router.post("/students/{student_id}/topics/{topic_id}/practice", response_model=PracticeSetRead, status_code=201)
def generate_practice(
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: GeneratePracticeRequest,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
    provider: AIProvider = Depends(get_provider),
) -> PracticeSetRead:
    if student.id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    ps = practice_service.generate_practice_set(
        db, student, provider, topic_id, data.easy_count, data.medium_count, data.hard_count
    )
    return _set_read(db, ps)


@router.get("/practice-sets/{practice_set_id}", response_model=PracticeSetRead)
def get_practice_set(
    practice_set_id: uuid.UUID, db: Session = Depends(get_db), student: User = Depends(require_student)
) -> PracticeSetRead:
    ps = practice_service.get_owned_practice_set(db, student, practice_set_id)
    return _set_read(db, ps)


@router.post("/practice-sets/{practice_set_id}/responses", response_model=PracticeResponseRead)
def submit_response(
    practice_set_id: uuid.UUID,
    data: PracticeResponseSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> PracticeResponseRead:
    response = practice_service.submit_practice_response(db, student, practice_set_id, data)
    return PracticeResponseRead(question_id=response.practice_question_id)


@router.post("/practice-sets/{practice_set_id}/complete", response_model=PracticeCompletionRead)
def complete_practice(
    practice_set_id: uuid.UUID, db: Session = Depends(get_db), student: User = Depends(require_student)
) -> PracticeCompletionRead:
    ps, responses = practice_service.complete_practice_set(db, student, practice_set_id)
    mastery_after = ps.mastery_after if ps.mastery_after is not None else ps.mastery_before
    return PracticeCompletionRead(
        practice_set=_set_read(db, ps),
        responses=[
            PracticeResponseGradedRead(
                question_id=r.practice_question_id,
                selected_option_id=r.selected_option_id,
                response_text=r.response_text,
                is_correct=r.is_correct,
                score=r.score,
            )
            for r in responses
        ],
        mastery_before=ps.mastery_before,
        mastery_after=mastery_after,
        delta=round(mastery_after - ps.mastery_before, 2),
    )
