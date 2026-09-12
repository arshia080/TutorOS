import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.batch import BatchStudentStatus


class BatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    grade: str | None = None
    section: str | None = None
    academic_year: str | None = None


class BatchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    grade: str | None = None
    section: str | None = None
    academic_year: str | None = None


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    teacher_id: uuid.UUID
    name: str
    grade: str | None
    section: str | None
    academic_year: str | None
    created_at: datetime
    student_count: int = 0


class BatchStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: uuid.UUID
    name: str
    email: str
    status: BatchStudentStatus
    joined_at: datetime


class AddStudentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
