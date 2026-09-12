import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AttentionPanelEntry,
    ClassPerformanceRead,
    QuestionAnalyticsRead,
    StudentPerformanceRead,
    TopicPerformanceRead,
)
from app.services import analytics_service as svc
from app.services import assessment_service
from app.services import batch_service
from app.services import student_service

router = APIRouter(tags=["analytics"])
require_teacher = require_role(UserRole.TEACHER)


def _authorize_student_access(db: Session, current_user: User, student_id: uuid.UUID) -> None:
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    elif current_user.role == UserRole.TEACHER:
        student_service.get_student_for_teacher(db, current_user, student_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("/students/{student_id}/performance", response_model=StudentPerformanceRead)
def get_student_performance(
    student_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> StudentPerformanceRead:
    _authorize_student_access(db, current_user, student_id)
    return svc.compute_student_performance(db, student_id)


@router.get("/students/{student_id}/topics/{topic_id}/performance", response_model=TopicPerformanceRead)
def get_student_topic_performance(
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TopicPerformanceRead:
    _authorize_student_access(db, current_user, student_id)
    perf = svc.compute_topic_performance(db, student_id, topic_id)
    if perf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No performance data for this topic yet")
    return perf


@router.get("/batches/{batch_id}/attention-panel", response_model=list[AttentionPanelEntry])
def get_attention_panel(
    batch_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[AttentionPanelEntry]:
    batch_service.get_owned_batch(db, teacher, batch_id)
    return svc.attention_panel(db, batch_id)


@router.get("/batches/{batch_id}/class-performance", response_model=ClassPerformanceRead)
def get_class_performance(
    batch_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> ClassPerformanceRead:
    batch_service.get_owned_batch(db, teacher, batch_id)
    return svc.class_performance(db, batch_id)


@router.get("/assessments/{assessment_id}/analytics", response_model=list[QuestionAnalyticsRead])
def get_question_analytics(
    assessment_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[QuestionAnalyticsRead]:
    assessment_service.get_owned_assessment(db, teacher, assessment_id)
    return svc.question_analytics(db, assessment_id)
