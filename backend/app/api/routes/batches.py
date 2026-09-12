import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.batch import (
    AddStudentRequest,
    BatchCreate,
    BatchRead,
    BatchStudentRead,
    BatchUpdate,
)
from app.services import batch_service

router = APIRouter(prefix="/batches", tags=["batches"])
require_teacher = require_role(UserRole.TEACHER)


def _to_batch_read(batch, db: Session) -> BatchRead:
    read = BatchRead.model_validate(batch)
    read.student_count = batch_service.student_count(db, batch.id)
    return read


@router.post("", response_model=BatchRead, status_code=201)
def create_batch(
    data: BatchCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> BatchRead:
    batch = batch_service.create_batch(db, teacher, data)
    return _to_batch_read(batch, db)


@router.get("", response_model=list[BatchRead])
def list_batches(
    db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[BatchRead]:
    return [_to_batch_read(b, db) for b in batch_service.list_batches(db, teacher)]


@router.get("/{batch_id}", response_model=BatchRead)
def get_batch(
    batch_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> BatchRead:
    batch = batch_service.get_owned_batch(db, teacher, batch_id)
    return _to_batch_read(batch, db)


@router.patch("/{batch_id}", response_model=BatchRead)
def update_batch(
    batch_id: uuid.UUID,
    data: BatchUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> BatchRead:
    batch = batch_service.update_batch(db, teacher, batch_id, data)
    return _to_batch_read(batch, db)


@router.get("/{batch_id}/students", response_model=list[BatchStudentRead])
def list_batch_students(
    batch_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[BatchStudentRead]:
    rows = batch_service.list_batch_students(db, teacher, batch_id)
    return [
        BatchStudentRead(
            student_id=user.id,
            name=user.name,
            email=user.email,
            status=link.status,
            joined_at=link.joined_at,
        )
        for link, user in rows
    ]


@router.post("/{batch_id}/students", response_model=BatchStudentRead, status_code=201)
def add_student(
    batch_id: uuid.UUID,
    data: AddStudentRequest,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> BatchStudentRead:
    link = batch_service.add_student_to_batch(db, teacher, batch_id, data)
    student = db.get(User, link.student_id)
    return BatchStudentRead(
        student_id=student.id,
        name=student.name,
        email=student.email,
        status=link.status,
        joined_at=link.joined_at,
    )
