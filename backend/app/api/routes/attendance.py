import uuid
from datetime import date as date_

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.batch import BatchStudent, BatchStudentStatus
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AttendanceMarkRequest,
    AttendanceRecordRead,
    StudentAttendanceRead,
)
from app.services import analytics_service as svc
from app.services import batch_service
from app.services import student_service

router = APIRouter(tags=["attendance"])
require_teacher = require_role(UserRole.TEACHER)


@router.post("/batches/{batch_id}/attendance", status_code=204)
def mark_attendance(
    batch_id: uuid.UUID,
    data: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> None:
    batch_service.get_owned_batch(db, teacher, batch_id)

    student_ids = {
        row[0]
        for row in db.query(BatchStudent.student_id)
        .filter(BatchStudent.batch_id == batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .all()
    }
    for entry in data.records:
        if entry.student_id not in student_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Student {entry.student_id} is not an active member of this batch",
            )

    svc.mark_attendance(db, batch_id, data.date, [(e.student_id, e.status) for e in data.records])


@router.get("/batches/{batch_id}/attendance", response_model=list[AttendanceRecordRead])
def get_attendance(
    batch_id: uuid.UUID,
    date: date_,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[AttendanceRecordRead]:
    batch_service.get_owned_batch(db, teacher, batch_id)
    records = svc.get_attendance_for_date(db, batch_id, date)
    return [AttendanceRecordRead(student_id=r.student_id, date=r.date, status=r.status) for r in records]


@router.get("/students/{student_id}/attendance", response_model=StudentAttendanceRead)
def get_student_attendance(
    student_id: uuid.UUID,
    batch_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudentAttendanceRead:
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    elif current_user.role == UserRole.TEACHER:
        student_service.get_student_for_teacher(db, current_user, student_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    result = svc.student_attendance_percentage(db, student_id, batch_id)
    return StudentAttendanceRead(
        student_id=result["student_id"],
        total_days=result["total_days"],
        present_days=result["present_days"],
        attendance_percentage=result["attendance_percentage"],
        records=[AttendanceRecordRead(student_id=r.student_id, date=r.date, status=r.status) for r in result["records"]],
    )
