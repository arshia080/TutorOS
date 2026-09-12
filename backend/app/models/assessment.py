import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AssessmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class QuestionType(str, enum.Enum):
    MCQ = "MCQ"
    MULTI_SELECT = "MULTI_SELECT"
    TRUE_FALSE = "TRUE_FALSE"
    NUMERICAL = "NUMERICAL"
    SHORT_ANSWER = "SHORT_ANSWER"
    LONG_ANSWER = "LONG_ANSWER"


# Graded automatically by comparing stored correct answers -- never by trusting the client.
OBJECTIVE_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE, QuestionType.NUMERICAL}
# Represented as a pick from QuestionOption rows (as opposed to free text).
SELECTABLE_TYPES = {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE}


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_marks: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessment_status"), default=AssessmentStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type"), nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("topics.id"))
    difficulty: Mapped[str | None] = mapped_column(String(20))
    marks: Mapped[float] = mapped_column(nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id", name="uq_attempt_per_student"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, name="attempt_status"), default=AttemptStatus.IN_PROGRESS, nullable=False
    )
    total_score: Mapped[float | None] = mapped_column()


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_response_per_question"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("questions.id"), nullable=False, index=True)
    response_text: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column()
    is_correct: Mapped[bool | None] = mapped_column()
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ResponseSelectedOption(Base):
    """Join table for selectable question types (MCQ/TRUE_FALSE store one row here,
    MULTI_SELECT stores one row per chosen option). A plain nullable FK column on
    Response can't represent multi-select, so this replaces the single
    `selected_option` field the literal spec schema sketches.
    """

    __tablename__ = "response_selected_options"

    response_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("responses.id", ondelete="CASCADE"), primary_key=True
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("question_options.id", ondelete="CASCADE"), primary_key=True
    )
