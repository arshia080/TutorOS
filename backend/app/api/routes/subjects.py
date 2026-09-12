import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectRead, TopicCreate, TopicRead
from app.services import subject_service

router = APIRouter(tags=["subjects"])
require_teacher = require_role(UserRole.TEACHER)


@router.post("/subjects", response_model=SubjectRead, status_code=201)
def create_subject(
    data: SubjectCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> SubjectRead:
    return subject_service.create_subject(db, data)


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(
    db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[SubjectRead]:
    return subject_service.list_subjects(db)


@router.post("/topics", response_model=TopicRead, status_code=201)
def create_topic(
    data: TopicCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> TopicRead:
    return subject_service.create_topic(db, data)


@router.get("/topics", response_model=list[TopicRead])
def list_topics(
    subject_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[TopicRead]:
    return subject_service.list_topics(db, subject_id)
