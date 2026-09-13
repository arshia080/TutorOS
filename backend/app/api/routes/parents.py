import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.parent import ChildProgressRead, ChildRead, LinkRequestCreate, LinkRequestRead
from app.services import parent_service

router = APIRouter(prefix="/parents", tags=["parents"])
require_parent = require_role(UserRole.PARENT)


@router.post("/link-requests", response_model=LinkRequestRead, status_code=201)
def create_link_request(
    data: LinkRequestCreate, db: Session = Depends(get_db), parent: User = Depends(require_parent)
) -> LinkRequestRead:
    if data.code:
        return parent_service.redeem_invite_code(db, parent, data.code, data.relationship)
    return parent_service.request_link_by_email(db, parent, data.student_email, data.relationship)


@router.get("/children", response_model=list[ChildRead])
def list_children(db: Session = Depends(get_db), parent: User = Depends(require_parent)) -> list[ChildRead]:
    return parent_service.list_children(db, parent)


@router.get("/children/{student_id}/progress", response_model=ChildProgressRead)
def get_child_progress(
    student_id: uuid.UUID, db: Session = Depends(get_db), parent: User = Depends(require_parent)
) -> ChildProgressRead:
    return parent_service.get_child_progress(db, parent, student_id)
