import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.parent import LinkStatus, RemarkCategory, SyllabusStatus
from app.schemas.analytics import StudentPerformanceRead


class TeacherProfileUpdate(BaseModel):
    institute_name: str | None = Field(default=None, max_length=255)
    bio: str | None = None
    locality: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    pincode: str | None = Field(default=None, max_length=20)


class TeacherProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    institute_name: str | None
    bio: str | None
    locality: str | None
    city: str | None
    pincode: str | None


class TeacherSearchResult(BaseModel):
    teacher_id: uuid.UUID
    name: str
    institute_name: str | None
    bio: str | None
    locality: str | None
    city: str | None
    subjects: list[str]
    grades: list[str]


class LinkRequestCreate(BaseModel):
    """Either `code` (instant-approve invite flow) or `student_email` +
    `relationship` (pending, awaiting teacher approval) must be supplied.
    """

    code: str | None = Field(default=None, min_length=1, max_length=16)
    student_email: EmailStr | None = None
    relationship: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _one_flow_only(self) -> "LinkRequestCreate":
        if bool(self.code) == bool(self.student_email):
            raise ValueError("Provide exactly one of `code` or `student_email`")
        return self


class LinkRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID
    student_id: uuid.UUID
    relationship: str | None
    status: LinkStatus
    requested_at: datetime
    approved_at: datetime | None


class PendingLinkRequestRead(BaseModel):
    id: uuid.UUID
    parent_name: str
    parent_email: str
    student_id: uuid.UUID
    student_name: str
    relationship: str | None
    requested_at: datetime


class InviteCodeRead(BaseModel):
    code: str
    student_id: uuid.UUID
    expires_at: datetime


class ChildRead(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    grade: str | None
    relationship: str | None
    linked_since: datetime | None


class SyllabusSubjectProgress(BaseModel):
    subject_id: uuid.UUID
    subject_name: str
    total_topics: int
    completed_topics: int
    percentage: float


class RecentTestResult(BaseModel):
    assessment_id: uuid.UUID
    title: str
    total_marks: float
    score: float | None
    submitted_at: datetime | None


class RemarkRead(BaseModel):
    id: uuid.UUID
    teacher_name: str
    batch_id: uuid.UUID
    remark_text: str
    category: RemarkCategory
    created_at: datetime


class ChildProgressRead(BaseModel):
    student_id: uuid.UUID
    student_name: str
    performance: StudentPerformanceRead
    syllabus: list[SyllabusSubjectProgress]
    recent_tests: list[RecentTestResult]
    remarks: list[RemarkRead]


class SyllabusMarkRequest(BaseModel):
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    status: SyllabusStatus
    notes: str | None = None


class SyllabusTopicRead(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    status: SyllabusStatus
    completed_at: datetime | None
    notes: str | None


class TeacherRemarkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    remark_text: str
    category: RemarkCategory
    visible_to_parent: bool
    created_at: datetime


class RemarkCreate(BaseModel):
    batch_id: uuid.UUID
    remark_text: str = Field(min_length=1, max_length=2000)
    category: RemarkCategory = RemarkCategory.GENERAL
    visible_to_parent: bool = True
