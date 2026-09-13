import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.parent import SyllabusProgress, SyllabusStatus
from app.models.subject import Subject, Topic
from app.models.user import User
from app.schemas.parent import SyllabusMarkRequest, SyllabusTopicRead
from app.services import batch_service

TOPIC_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found for this subject")


def mark_topic(db: Session, teacher: User, topic_id: uuid.UUID, data: SyllabusMarkRequest) -> SyllabusTopicRead:
    # Ownership: the batch must be this teacher's own.
    batch_service.get_owned_batch(db, teacher, data.batch_id)

    topic = db.get(Topic, topic_id)
    if topic is None or topic.subject_id != data.subject_id:
        raise TOPIC_NOT_FOUND

    row = (
        db.query(SyllabusProgress)
        .filter(
            SyllabusProgress.batch_id == data.batch_id,
            SyllabusProgress.subject_id == data.subject_id,
            SyllabusProgress.topic_id == topic_id,
        )
        .first()
    )
    if row is None:
        row = SyllabusProgress(batch_id=data.batch_id, subject_id=data.subject_id, topic_id=topic_id)
        db.add(row)

    row.status = data.status
    row.notes = data.notes
    row.marked_by = teacher.id
    if data.status == SyllabusStatus.COMPLETED:
        row.completed_at = datetime.now(timezone.utc)
    else:
        row.completed_at = None

    db.commit()
    db.refresh(row)
    return SyllabusTopicRead(
        topic_id=row.topic_id,
        topic_name=topic.name,
        status=row.status,
        completed_at=row.completed_at,
        notes=row.notes,
    )


def list_syllabus(
    db: Session, teacher: User, batch_id: uuid.UUID, subject_id: uuid.UUID
) -> list[SyllabusTopicRead]:
    batch_service.get_owned_batch(db, teacher, batch_id)

    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    topics = db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.name).all()
    progress_by_topic = {
        row.topic_id: row
        for row in db.query(SyllabusProgress).filter(
            SyllabusProgress.batch_id == batch_id, SyllabusProgress.subject_id == subject_id
        )
    }

    result = []
    for topic in topics:
        row = progress_by_topic.get(topic.id)
        result.append(
            SyllabusTopicRead(
                topic_id=topic.id,
                topic_name=topic.name,
                status=row.status if row else SyllabusStatus.NOT_STARTED,
                completed_at=row.completed_at if row else None,
                notes=row.notes if row else None,
            )
        )
    return result
