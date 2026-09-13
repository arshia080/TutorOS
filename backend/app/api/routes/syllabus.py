import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.parent import SyllabusMarkRequest, SyllabusTopicRead
from app.services import syllabus_service

router = APIRouter(tags=["syllabus"])
require_teacher = require_role(UserRole.TEACHER)


@router.post("/syllabus/{topic_id}/mark-complete", response_model=SyllabusTopicRead)
def mark_topic(
    topic_id: uuid.UUID,
    data: SyllabusMarkRequest,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> SyllabusTopicRead:
    return syllabus_service.mark_topic(db, teacher, topic_id, data)


@router.get("/batches/{batch_id}/subjects/{subject_id}/syllabus", response_model=list[SyllabusTopicRead])
def get_syllabus(
    batch_id: uuid.UUID,
    subject_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[SyllabusTopicRead]:
    return syllabus_service.list_syllabus(db, teacher, batch_id, subject_id)
