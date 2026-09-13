import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.parent import (
    InviteCodeRead,
    LinkRequestRead,
    PendingLinkRequestRead,
    TeacherProfileRead,
    TeacherProfileUpdate,
    TeacherSearchResult,
)
from app.services import parent_service, student_service, teacher_search_service

router = APIRouter(prefix="/teachers", tags=["teachers"])
require_teacher = require_role(UserRole.TEACHER)


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> dict:
    return student_service.teacher_overview_counts(db, teacher)


# ---------------------------------------------------------------------------
# Public-ish teacher discovery (Phase 8) -- no batch/assessment/student data
# ever leaves teacher_search_service, only aggregate public profile info.
# ---------------------------------------------------------------------------


@router.get("/search", response_model=list[TeacherSearchResult])
def search_teachers(
    locality: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TeacherSearchResult]:
    return teacher_search_service.search_teachers(db, locality=locality, subject=subject, grade=grade)


@router.get("/profile", response_model=TeacherProfileRead)
def get_my_profile(db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> TeacherProfileRead:
    profile = teacher_search_service.get_own_profile(db, teacher)
    if profile is None:
        return TeacherProfileRead(institute_name=None, bio=None, locality=None, city=None, pincode=None)
    return TeacherProfileRead.model_validate(profile)


@router.patch("/profile", response_model=TeacherProfileRead)
def update_my_profile(
    data: TeacherProfileUpdate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> TeacherProfileRead:
    profile = teacher_search_service.upsert_teacher_profile(db, teacher, data)
    return TeacherProfileRead.model_validate(profile)


# ---------------------------------------------------------------------------
# Parent link-request approval (Phase 8) -- scoped to students this teacher
# actually teaches; see parent_service module docstring for the full flow.
# ---------------------------------------------------------------------------


@router.get("/link-requests", response_model=list[PendingLinkRequestRead])
def list_link_requests(
    db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[PendingLinkRequestRead]:
    return parent_service.list_pending_requests_for_teacher(db, teacher)


@router.post("/link-requests/{link_id}/approve", response_model=LinkRequestRead)
def approve_link_request(
    link_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> LinkRequestRead:
    return parent_service.approve_link(db, teacher, link_id)


@router.post("/link-requests/{link_id}/reject", response_model=LinkRequestRead)
def reject_link_request(
    link_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> LinkRequestRead:
    return parent_service.reject_link(db, teacher, link_id)


@router.post("/students/{student_id}/invite-code", response_model=InviteCodeRead)
def create_invite_code(
    student_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> InviteCodeRead:
    invite = parent_service.generate_invite_code(db, teacher, student_id)
    return InviteCodeRead(code=invite.code, student_id=invite.student_id, expires_at=invite.expires_at)
