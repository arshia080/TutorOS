import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.batch import Batch, BatchStudent, BatchStudentStatus
from app.models.user import User, UserRole
from app.schemas.batch import AddStudentRequest, BatchCreate, BatchUpdate

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


def create_batch(db: Session, teacher: User, data: BatchCreate) -> Batch:
    batch = Batch(teacher_id=teacher.id, **data.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def list_batches(db: Session, teacher: User) -> list[Batch]:
    return db.query(Batch).filter(Batch.teacher_id == teacher.id).order_by(Batch.created_at).all()


def get_owned_batch(db: Session, teacher: User, batch_id: uuid.UUID) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None or batch.teacher_id != teacher.id:
        raise NOT_FOUND
    return batch


def update_batch(db: Session, teacher: User, batch_id: uuid.UUID, data: BatchUpdate) -> Batch:
    batch = get_owned_batch(db, teacher, batch_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(batch, field, value)
    db.commit()
    db.refresh(batch)
    return batch


def student_count(db: Session, batch_id: uuid.UUID) -> int:
    return (
        db.query(func.count(BatchStudent.student_id))
        .filter(BatchStudent.batch_id == batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .scalar()
    )


def list_batch_students(db: Session, teacher: User, batch_id: uuid.UUID) -> list[tuple[BatchStudent, User]]:
    get_owned_batch(db, teacher, batch_id)
    return (
        db.query(BatchStudent, User)
        .join(User, User.id == BatchStudent.student_id)
        .filter(BatchStudent.batch_id == batch_id)
        .order_by(BatchStudent.joined_at)
        .all()
    )


def add_student_to_batch(
    db: Session, teacher: User, batch_id: uuid.UUID, data: AddStudentRequest
) -> BatchStudent:
    batch = get_owned_batch(db, teacher, batch_id)

    student = db.query(User).filter(User.email == data.email).first()
    if student is not None and student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email belongs to a non-student account"
        )

    if student is None:
        # ponytail: no invite/reset-password flow yet; the account is created with a
        # random password the student can't retrieve. Real credential delivery (invite
        # email or teacher-set temp password) is deferred until it's actually needed.
        student = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(secrets.token_urlsafe(16)),
            role=UserRole.STUDENT,
        )
        db.add(student)
        db.flush()

    existing_link = db.get(BatchStudent, {"batch_id": batch.id, "student_id": student.id})
    if existing_link is not None:
        if existing_link.status == BatchStudentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Student already in this batch"
            )
        existing_link.status = BatchStudentStatus.ACTIVE
        db.commit()
        db.refresh(existing_link)
        return existing_link

    link = BatchStudent(batch_id=batch.id, student_id=student.id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
