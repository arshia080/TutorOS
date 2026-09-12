import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.assessment import QuestionType
from app.models.practice import PracticeSetStatus


class GeneratePracticeRequest(BaseModel):
    easy_count: int | None = Field(default=None, ge=0, le=20)
    medium_count: int | None = Field(default=None, ge=0, le=20)
    hard_count: int | None = Field(default=None, ge=0, le=20)


class PracticeOptionRead(BaseModel):
    id: uuid.UUID
    option_text: str
    is_correct: bool | None = None  # omitted while the set is IN_PROGRESS


class PracticeQuestionRead(BaseModel):
    id: uuid.UUID
    question_text: str
    question_type: QuestionType
    difficulty: str
    marks: float
    order_index: int
    options: list[PracticeOptionRead] = []


class PracticeResponseSubmit(BaseModel):
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    response_text: str | None = None


class PracticeResponseRead(BaseModel):
    question_id: uuid.UUID
    saved: bool = True


class PracticeResponseGradedRead(BaseModel):
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None
    response_text: str | None
    is_correct: bool
    score: float


class PracticeSetRead(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    topic_name: str
    title: str
    difficulty: str
    status: PracticeSetStatus
    mastery_before: float
    mastery_after: float | None
    created_at: datetime
    completed_at: datetime | None
    questions: list[PracticeQuestionRead] = []


class PracticeCompletionRead(BaseModel):
    practice_set: PracticeSetRead
    responses: list[PracticeResponseGradedRead]
    mastery_before: float
    mastery_after: float
    delta: float
    note: str = (
        "This is an observed change on this practice set, not proof that the practice caused it -- "
        "mastery naturally varies between attempts."
    )
