import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.batch import Batch, BatchStudent, BatchStudentStatus
from app.models.homework import Homework, HomeworkAttachment, HomeworkSubmission, SubmissionStatus
from app.models.subject import Subject, Topic
from app.models.user import User, UserRole
from app.schemas.homework import HomeworkUpdate
from app.services.upload_service import UploadedFile

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Homework not found")


def _is_active_student(db: Session, batch_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    link = db.get(BatchStudent, {"batch_id": batch_id, "student_id": student_id})
    return link is not None and link.status == BatchStudentStatus.ACTIVE


def create_homework(
    db: Session,
    teacher: User,
    batch_id: uuid.UUID,
    subject_id: uuid.UUID,
    topic_id: uuid.UUID | None,
    title: str,
    description: str | None,
    due_date: datetime,
    uploaded_files: list[UploadedFile],
) -> Homework:
    batch = db.get(Batch, batch_id)
    if batch is None or batch.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if db.get(Subject, subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    if topic_id is not None and db.get(Topic, topic_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    homework = Homework(
        teacher_id=teacher.id,
        batch_id=batch_id,
        subject_id=subject_id,
        topic_id=topic_id,
        title=title,
        description=description,
        due_date=due_date,
    )
    db.add(homework)
    db.flush()

    for f in uploaded_files:
        db.add(
            HomeworkAttachment(
                homework_id=homework.id,
                file_name=f.file_name,
                storage_key=f.storage_key,
                mime_type=f.mime_type,
                file_size=f.file_size,
            )
        )

    db.commit()
    db.refresh(homework)
    return homework


def list_homework_for_teacher(db: Session, teacher: User) -> list[Homework]:
    return db.query(Homework).filter(Homework.teacher_id == teacher.id).order_by(Homework.due_date).all()


def list_homework_for_student(db: Session, student: User) -> list[Homework]:
    return (
        db.query(Homework)
        .join(BatchStudent, BatchStudent.batch_id == Homework.batch_id)
        .filter(
            BatchStudent.student_id == student.id,
            BatchStudent.status == BatchStudentStatus.ACTIVE,
        )
        .order_by(Homework.due_date)
        .all()
    )


def get_homework_scoped(db: Session, user: User, homework_id: uuid.UUID) -> Homework:
    homework = db.get(Homework, homework_id)
    if homework is None:
        raise NOT_FOUND

    if user.role == UserRole.TEACHER:
        if homework.teacher_id != user.id:
            raise NOT_FOUND
    elif user.role == UserRole.STUDENT:
        if not _is_active_student(db, homework.batch_id, user.id):
            raise NOT_FOUND
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return homework


def get_owned_homework(db: Session, teacher: User, homework_id: uuid.UUID) -> Homework:
    homework = db.get(Homework, homework_id)
    if homework is None or homework.teacher_id != teacher.id:
        raise NOT_FOUND
    return homework


def update_homework(db: Session, teacher: User, homework_id: uuid.UUID, data: HomeworkUpdate) -> Homework:
    homework = get_owned_homework(db, teacher, homework_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(homework, field, value)
    db.commit()
    db.refresh(homework)
    return homework


def get_attachment_scoped(
    db: Session, user: User, homework_id: uuid.UUID, attachment_id: uuid.UUID
) -> HomeworkAttachment:
    get_homework_scoped(db, user, homework_id)
    attachment = db.get(HomeworkAttachment, attachment_id)
    if attachment is None or attachment.homework_id != homework_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


def submit_homework(
    db: Session, student: User, homework_id: uuid.UUID, uploaded: UploadedFile
) -> HomeworkSubmission:
    homework = db.get(Homework, homework_id)
    if homework is None or not _is_active_student(db, homework.batch_id, student.id):
        raise NOT_FOUND

    now = datetime.now(timezone.utc)
    due_date = homework.due_date if homework.due_date.tzinfo else homework.due_date.replace(tzinfo=timezone.utc)
    is_late = now > due_date

    if is_late and not homework.allow_late_submissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The deadline has passed and this homework does not accept late submissions",
        )

    existing = (
        db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.homework_id == homework_id, HomeworkSubmission.student_id == student.id)
        .first()
    )

    status_value = SubmissionStatus.LATE if is_late else SubmissionStatus.SUBMITTED
    if existing is not None:
        existing.submitted_at = now
        existing.status = status_value
        existing.file_name = uploaded.file_name
        existing.storage_key = uploaded.storage_key
        existing.mime_type = uploaded.mime_type
        existing.file_size = uploaded.file_size
        db.commit()
        db.refresh(existing)
        return existing

    submission = HomeworkSubmission(
        homework_id=homework_id,
        student_id=student.id,
        submitted_at=now,
        status=status_value,
        file_name=uploaded.file_name,
        storage_key=uploaded.storage_key,
        mime_type=uploaded.mime_type,
        file_size=uploaded.file_size,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def get_submission_scoped(
    db: Session, user: User, homework_id: uuid.UUID, student_id: uuid.UUID
) -> HomeworkSubmission:
    get_homework_scoped(db, user, homework_id)

    if user.role == UserRole.STUDENT and user.id != student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    submission = (
        db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.homework_id == homework_id, HomeworkSubmission.student_id == student_id)
        .first()
    )
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


def list_submission_roster(db: Session, teacher: User, homework_id: uuid.UUID) -> list[dict]:
    homework = get_owned_homework(db, teacher, homework_id)

    roster = (
        db.query(User, HomeworkSubmission)
        .join(BatchStudent, BatchStudent.student_id == User.id)
        .outerjoin(
            HomeworkSubmission,
            (HomeworkSubmission.student_id == User.id) & (HomeworkSubmission.homework_id == homework_id),
        )
        .filter(BatchStudent.batch_id == homework.batch_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .order_by(User.name)
        .all()
    )

    return [
        {
            "student_id": user.id,
            "name": user.name,
            "email": user.email,
            "status": submission.status if submission else None,
            "submitted_at": submission.submitted_at if submission else None,
        }
        for user, submission in roster
    ]
