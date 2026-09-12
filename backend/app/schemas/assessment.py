import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.assessment import AssessmentStatus, AttemptStatus, QuestionType


class AssessmentCreate(BaseModel):
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    total_marks: float = Field(gt=0)


class AssessmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    total_marks: float | None = Field(default=None, gt=0)
    status: AssessmentStatus | None = None


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    teacher_id: uuid.UUID
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    title: str
    description: str | None
    duration_minutes: int
    total_marks: float
    status: AssessmentStatus
    created_at: datetime


class QuestionOptionCreate(BaseModel):
    option_text: str = Field(min_length=1)
    is_correct: bool = False


class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    question_type: QuestionType
    topic_id: uuid.UUID | None = None
    difficulty: str | None = None
    marks: float = Field(gt=0)
    explanation: str | None = None
    options: list[QuestionOptionCreate] = []


class QuestionOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    option_text: str
    order_index: int
    is_correct: bool | None = None  # omitted from output for a student mid-attempt


class QuestionUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=1)
    topic_id: uuid.UUID | None = None
    difficulty: str | None = None
    marks: float | None = Field(default=None, gt=0)
    explanation: str | None = None
    options: list[QuestionOptionCreate] | None = None  # when given, replaces the whole option set


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    question_text: str
    question_type: QuestionType
    topic_id: uuid.UUID | None
    difficulty: str | None
    marks: float
    order_index: int
    explanation: str | None = None
    source: str = "MANUAL"
    options: list[QuestionOptionRead] = []


class PublishError(BaseModel):
    errors: list[str]


class StartAttemptResponse(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    status: AttemptStatus
    started_at: datetime
    duration_minutes: int
    deadline: datetime
    questions: list[QuestionRead]


class ResponseSubmit(BaseModel):
    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] | None = None
    response_text: str | None = None
    time_spent_seconds: int | None = None
    marked_for_review: bool = False


class ResponseRead(BaseModel):
    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] = []
    response_text: str | None = None
    marked_for_review: bool
    saved: bool = True


class ResponseGradedRead(BaseModel):
    """Full detail including score -- only ever shown to the owning student after
    finalization, or to the teacher who owns the assessment.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    response_text: str | None
    score: float | None
    is_correct: bool | None
    selected_option_ids: list[uuid.UUID] = []


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime
    submitted_at: datetime | None
    status: AttemptStatus
    total_score: float | None


class GradeRequest(BaseModel):
    score: float = Field(ge=0)


class AttemptReview(BaseModel):
    """Only returned once an attempt is finalized -- correct answers and scores
    are withheld while status is IN_PROGRESS.
    """

    attempt: AttemptRead
    questions: list[QuestionRead]
    responses: list[ResponseGradedRead]
