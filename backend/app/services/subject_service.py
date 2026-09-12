import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.subject import Subject, Topic
from app.schemas.subject import SubjectCreate, TopicCreate


def create_subject(db: Session, data: SubjectCreate) -> Subject:
    subject = Subject(**data.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


def list_subjects(db: Session) -> list[Subject]:
    return db.query(Subject).order_by(Subject.name).all()


def create_topic(db: Session, data: TopicCreate) -> Topic:
    subject = db.get(Subject, data.subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    topic = Topic(**data.model_dump())
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def list_topics(db: Session, subject_id: uuid.UUID | None) -> list[Topic]:
    query = db.query(Topic)
    if subject_id is not None:
        query = query.filter(Topic.subject_id == subject_id)
    return query.order_by(Topic.name).all()
