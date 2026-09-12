import uuid

from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    grade: str | None = None


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    grade: str | None


class TopicCreate(BaseModel):
    subject_id: uuid.UUID
    chapter: str | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_id: uuid.UUID
    chapter: str | None
    name: str
    description: str | None
