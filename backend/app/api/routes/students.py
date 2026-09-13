import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.parent import RemarkCreate, TeacherRemarkRead
from app.schemas.student import StudentRead
from app.services import remark_service, student_service

router = APIRouter(prefix="/students", tags=["students"])
require_teacher = require_role(UserRole.TEACHER)


def _to_student_read(db: Session, student: User) -> StudentRead:
    profile = student_service.get_student_profile(db, student.id)
    return StudentRead(
        id=student.id,
        name=student.name,
        email=student.email,
        created_at=student.created_at,
        grade=profile.grade if profile else None,
        academic_year=profile.academic_year if profile else None,
    )


@router.get("", response_model=list[StudentRead])
def list_students(
    db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[StudentRead]:
    return [_to_student_read(db, s) for s in student_service.list_students_for_teacher(db, teacher)]


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudentRead:
    # A student may view their own record; a teacher may view students in their own batches.
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        return _to_student_read(db, current_user)

    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    student = student_service.get_student_for_teacher(db, current_user, student_id)
    return _to_student_read(db, student)


@router.post("/{student_id}/remarks", response_model=TeacherRemarkRead, status_code=201)
def add_remark(
    student_id: uuid.UUID,
    data: RemarkCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> TeacherRemarkRead:
    remark = remark_service.create_remark(db, teacher, student_id, data)
    return TeacherRemarkRead.model_validate(remark)


@router.get("/{student_id}/remarks", response_model=list[TeacherRemarkRead])
def list_remarks(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[TeacherRemarkRead]:
    remarks = remark_service.list_remarks_for_teacher(db, teacher, student_id)
    return [TeacherRemarkRead.model_validate(r) for r in remarks]
