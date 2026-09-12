import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ExtractionJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIExtractionJob(Base):
    """Tracks a PDF-to-assessment background job so the triggering HTTP request
    can return immediately with a job id and the teacher can poll for status
    (product spec section 13). Not in the spec's literal table list (section 7)
    -- necessary to satisfy "returns immediately with a job ID; the teacher
    polls" at all, the same way Phase 2's storage abstraction and Phase 4's
    performance_snapshots extended the literal schema where the behavior
    required it.
    """

    __tablename__ = "ai_extraction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False)
    status: Mapped[ExtractionJobStatus] = mapped_column(
        Enum(ExtractionJobStatus, name="extraction_job_status"), default=ExtractionJobStatus.PENDING, nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("assessments.id"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column()
