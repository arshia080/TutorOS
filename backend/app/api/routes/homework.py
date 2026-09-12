import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.homework import Homework, HomeworkAttachment, HomeworkSubmission
from app.models.user import User, UserRole
from app.schemas.homework import (
    HomeworkAttachmentRead,
    HomeworkRead,
    HomeworkUpdate,
    RosterEntry,
    SubmissionRead,
)
from app.services import homework_service
from app.services.upload_service import save_upload
from app.storage import get_storage

router = APIRouter(prefix="/homework", tags=["homework"])
require_teacher = require_role(UserRole.TEACHER)
require_student = require_role(UserRole.STUDENT)


def _parse_due_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="due_date must be a valid ISO 8601 datetime")


def _to_homework_read(db: Session, homework: Homework) -> HomeworkRead:
    attachments = (
        db.query(HomeworkAttachment).filter(HomeworkAttachment.homework_id == homework.id).all()
    )
    read = HomeworkRead.model_validate(homework)
    read.attachments = [HomeworkAttachmentRead.model_validate(a) for a in attachments]
    return read


@router.post("", response_model=HomeworkRead, status_code=201)
async def create_homework(
    batch_id: uuid.UUID = Form(...),
    subject_id: uuid.UUID = Form(...),
    topic_id: uuid.UUID | None = Form(None),
    title: str = Form(...),
    description: str | None = Form(None),
    due_date: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> HomeworkRead:
    uploaded = [await save_upload(f) for f in files if f.filename]
    homework = homework_service.create_homework(
        db, teacher, batch_id, subject_id, topic_id, title, description, _parse_due_date(due_date), uploaded
    )
    return _to_homework_read(db, homework)


@router.get("", response_model=list[HomeworkRead])
def list_homework(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[HomeworkRead]:
    if current_user.role == UserRole.TEACHER:
        items = homework_service.list_homework_for_teacher(db, current_user)
    elif current_user.role == UserRole.STUDENT:
        items = homework_service.list_homework_for_student(db, current_user)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return [_to_homework_read(db, h) for h in items]


@router.get("/{homework_id}", response_model=HomeworkRead)
def get_homework(
    homework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HomeworkRead:
    homework = homework_service.get_homework_scoped(db, current_user, homework_id)
    return _to_homework_read(db, homework)


@router.patch("/{homework_id}", response_model=HomeworkRead)
def update_homework(
    homework_id: uuid.UUID,
    data: HomeworkUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> HomeworkRead:
    homework = homework_service.update_homework(db, teacher, homework_id, data)
    return _to_homework_read(db, homework)


@router.get("/{homework_id}/attachments/{attachment_id}/file")
def download_attachment(
    homework_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    attachment = homework_service.get_attachment_scoped(db, current_user, homework_id, attachment_id)
    content = get_storage().read(attachment.storage_key)
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'},
    )


@router.post("/{homework_id}/submissions", response_model=SubmissionRead, status_code=201)
async def submit_homework(
    homework_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> SubmissionRead:
    uploaded = await save_upload(file)
    return homework_service.submit_homework(db, student, homework_id, uploaded)


@router.get("/{homework_id}/submissions", response_model=list[RosterEntry])
def list_submissions(
    homework_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)
) -> list[RosterEntry]:
    return homework_service.list_submission_roster(db, teacher, homework_id)


@router.get("/{homework_id}/submissions/me", response_model=SubmissionRead)
def get_my_submission(
    homework_id: uuid.UUID, db: Session = Depends(get_db), student: User = Depends(require_student)
) -> SubmissionRead:
    return homework_service.get_submission_scoped(db, student, homework_id, student.id)


@router.get("/{homework_id}/submissions/{student_id}", response_model=SubmissionRead)
def get_submission(
    homework_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionRead:
    return homework_service.get_submission_scoped(db, current_user, homework_id, student_id)


@router.get("/{homework_id}/submissions/{student_id}/file")
def download_submission(
    homework_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    submission = homework_service.get_submission_scoped(db, current_user, homework_id, student_id)
    content = get_storage().read(submission.storage_key)
    return Response(
        content=content,
        media_type=submission.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{submission.file_name}"'},
    )
