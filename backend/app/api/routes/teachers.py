from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import student_service

router = APIRouter(prefix="/teachers", tags=["teachers"])
require_teacher = require_role(UserRole.TEACHER)


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> dict:
    return student_service.teacher_overview_counts(db, teacher)
