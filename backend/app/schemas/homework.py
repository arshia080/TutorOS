import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.homework import SubmissionStatus


class HomeworkUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    allow_late_submissions: bool | None = None


class HomeworkAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    mime_type: str
    file_size: int


class HomeworkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None
    title: str
    description: str | None
    due_date: datetime
    allow_late_submissions: bool
    created_at: datetime
    attachments: list[HomeworkAttachmentRead] = []


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    homework_id: uuid.UUID
    student_id: uuid.UUID
    submitted_at: datetime
    status: SubmissionStatus
    file_name: str
    mime_type: str
    file_size: int
    score: float | None
    feedback: str | None


class RosterEntry(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    status: SubmissionStatus | None  # None means not submitted yet (pending)
    submitted_at: datetime | None
