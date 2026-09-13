import uuid

from sqlalchemy.orm import Session

from app.models.parent import Remark
from app.models.user import User
from app.schemas.parent import RemarkCreate
from app.services import batch_service, student_service


def create_remark(db: Session, teacher: User, student_id: uuid.UUID, data: RemarkCreate) -> Remark:
    # Both ownership checks matter: the batch must be this teacher's own, AND
    # the student must actually be enrolled in one of this teacher's batches
    # (not necessarily *this* batch specifically, but scoped to the teacher).
    batch_service.get_owned_batch(db, teacher, data.batch_id)
    student_service.get_student_for_teacher(db, teacher, student_id)

    remark = Remark(
        student_id=student_id,
        teacher_id=teacher.id,
        batch_id=data.batch_id,
        remark_text=data.remark_text,
        category=data.category,
        visible_to_parent=data.visible_to_parent,
    )
    db.add(remark)
    db.commit()
    db.refresh(remark)
    return remark


def list_remarks_for_teacher(db: Session, teacher: User, student_id: uuid.UUID) -> list[Remark]:
    student_service.get_student_for_teacher(db, teacher, student_id)
    return (
        db.query(Remark)
        .filter(Remark.student_id == student_id, Remark.teacher_id == teacher.id)
        .order_by(Remark.created_at.desc())
        .all()
    )
