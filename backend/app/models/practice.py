import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.assessment import QuestionType

# ponytail: practice sets only support single-answer question types (MCQ,
# TRUE_FALSE, NUMERICAL) -- no MULTI_SELECT (would need a selected-options join
# table like Phase 3's ResponseSelectedOption) and no subjective types (would
# need teacher grading, breaking the immediate self-serve practice loop this
# feature exists for). Lift this by reusing Phase 3's join-table pattern if a
# real need for multi-select/subjective practice questions shows up.
PRACTICE_QUESTION_TYPES = {QuestionType.MCQ, QuestionType.TRUE_FALSE, QuestionType.NUMERICAL}


class PracticeSetStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class RecommendationStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class PracticeSet(Base):
    __tablename__ = "practice_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("topics.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="MIXED", nullable=False)
    status: Mapped[PracticeSetStatus] = mapped_column(
        Enum(PracticeSetStatus, name="practice_set_status"), default=PracticeSetStatus.IN_PROGRESS, nullable=False
    )
    # Snapshot of the topic's mastery_score at generation time / at completion
    # time -- the before/after comparison shown to the student. See
    # docs/analytics.md for exactly how mastery_after is derived.
    mastery_before: Mapped[float] = mapped_column(nullable=False)
    mastery_after: Mapped[float | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column()


class PracticeQuestion(Base):
    __tablename__ = "practice_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    practice_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("practice_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="practice_question_type"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    marks: Mapped[float] = mapped_column(nullable=False, default=1.0)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PracticeQuestionOption(Base):
    __tablename__ = "practice_question_options"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    practice_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("practice_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PracticeResponse(Base):
    __tablename__ = "practice_responses"
    __table_args__ = (UniqueConstraint("practice_set_id", "practice_question_id", name="uq_practice_response_per_question"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    practice_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("practice_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    practice_question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("practice_questions.id"), nullable=False, index=True
    )
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("practice_question_options.id"))
    response_text: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("topics.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), default="PRACTICE_SET", nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Larger gap below the weak-topic threshold -> higher priority. See
    # practice_service.py for the exact computation.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status"), default=RecommendationStatus.PENDING, nullable=False
    )
    practice_set_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("practice_sets.id"))
