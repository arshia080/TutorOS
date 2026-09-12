import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.batch import Batch, BatchStudent
from app.models.profile import StudentProfile
from app.models.user import User

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")


def list_students_for_teacher(db: Session, teacher: User) -> list[User]:
    return (
        db.query(User)
        .join(BatchStudent, BatchStudent.student_id == User.id)
        .join(Batch, Batch.id == BatchStudent.batch_id)
        .filter(Batch.teacher_id == teacher.id)
        .distinct()
        .order_by(User.name)
        .all()
    )


def get_student_for_teacher(db: Session, teacher: User, student_id: uuid.UUID) -> User:
    """Only students enrolled in one of this teacher's batches are visible."""
    student = (
        db.query(User)
        .join(BatchStudent, BatchStudent.student_id == User.id)
        .join(Batch, Batch.id == BatchStudent.batch_id)
        .filter(Batch.teacher_id == teacher.id, User.id == student_id)
        .first()
    )
    if student is None:
        raise NOT_FOUND
    return student


def get_student_profile(db: Session, student_id: uuid.UUID) -> StudentProfile | None:
    return db.query(StudentProfile).filter(StudentProfile.user_id == student_id).first()


def teacher_overview_counts(db: Session, teacher: User) -> dict:
    total_batches = db.query(Batch).filter(Batch.teacher_id == teacher.id).count()
    total_students = (
        db.query(User.id)
        .join(BatchStudent, BatchStudent.student_id == User.id)
        .join(Batch, Batch.id == BatchStudent.batch_id)
        .filter(Batch.teacher_id == teacher.id)
        .distinct()
        .count()
    )
    return {"total_batches": total_batches, "total_students": total_students}
