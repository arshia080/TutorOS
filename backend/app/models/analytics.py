import enum
import uuid
from datetime import date as date_, datetime, timezone

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"


class TrendDirection(str, enum.Enum):
    IMPROVING = "IMPROVING"
    DECLINING = "DECLINING"
    STABLE = "STABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PerformanceSnapshot(Base):
    """Materialized cache of compute_topic_performance() for one (student, topic).

    Written by the recalculation job; API reads always recompute live from
    responses/attempts (see app/services/analytics_service.py) so this table can
    never itself be a source of staleness bugs -- it exists so the schema
    requirement from the product spec is met and so a later phase (e.g. AI
    insights) can read precomputed numbers without recomputing on every request.
    """

    __tablename__ = "performance_snapshots"
    __table_args__ = (UniqueConstraint("student_id", "topic_id", name="uq_snapshot_per_student_topic"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("topics.id"), nullable=False, index=True)
    mastery_score: Mapped[float] = mapped_column(nullable=False)
    mastery_category: Mapped[str] = mapped_column(String(30), nullable=False)
    accuracy: Mapped[float] = mapped_column(nullable=False)
    recent_accuracy: Mapped[float] = mapped_column(nullable=False)
    historical_accuracy: Mapped[float] = mapped_column(nullable=False)
    difficulty_adjusted_accuracy: Mapped[float] = mapped_column(nullable=False)
    consistency_score: Mapped[float] = mapped_column(nullable=False)
    trend: Mapped[TrendDirection] = mapped_column(Enum(TrendDirection, name="trend_direction"), nullable=False)
    questions_attempted: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("batch_id", "student_id", "date", name="uq_attendance_per_day"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    date: Mapped[date_] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus, name="attendance_status"), nullable=False)
