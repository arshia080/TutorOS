import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.assessment import QuestionType


class AIGeneratedOption(BaseModel):
    option_text: str = Field(min_length=1)
    is_correct: bool


class AIGeneratedQuestion(BaseModel):
    """The structured shape we force the AI provider to return for both
    generation and PDF extraction. Structural correctness (types, required
    fields, enum membership) is enforced by Pydantic itself; option-shape
    rules (e.g. "MCQ needs exactly one correct option") are checked
    separately by validate_option_shape, shared with the Phase 3 publish
    validator, since Pydantic alone can't express "conditional on question_type".
    """

    question_text: str = Field(min_length=1)
    question_type: QuestionType
    difficulty: str = Field(min_length=1)
    marks: float = Field(gt=0)
    topic_name: str | None = None
    options: list[AIGeneratedOption] = []

    @field_validator("difficulty")
    @classmethod
    def _normalize_difficulty(cls, v: str) -> str:
        return v.strip().upper()


class AIGeneratedQuestionSet(BaseModel):
    questions: list[AIGeneratedQuestion] = Field(min_length=1)


class GenerateQuestionsRequest(BaseModel):
    batch_id: uuid.UUID
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None
    grade: str = Field(min_length=1)
    count: int = Field(gt=0, le=20)
    difficulty: str = Field(min_length=1)
    question_types: list[QuestionType] = Field(min_length=1)
    total_marks: float = Field(gt=0)
    duration_minutes: int = Field(gt=0)


class PDFExtractionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    assessment_id: uuid.UUID | None
    error_message: str | None


class StudentInsightRead(BaseModel):
    insight: str
