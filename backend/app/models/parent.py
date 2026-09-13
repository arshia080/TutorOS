import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class LinkStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SyllabusStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class RemarkCategory(str, enum.Enum):
    ACADEMIC = "ACADEMIC"
    BEHAVIOR = "BEHAVIOR"
    ATTENDANCE = "ATTENDANCE"
    GENERAL = "GENERAL"


class ParentProfile(Base):
    __tablename__ = "parent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(30))
    locality: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class ParentStudentLink(Base):
    """A parent only ever sees a child's data once status == APPROVED (enforced in
    parent_service, not here) -- PENDING/REJECTED rows exist purely so the request
    lifecycle is visible to the teacher who must act on it.
    """

    __tablename__ = "parent_student_links"
    __table_args__ = (UniqueConstraint("parent_id", "student_id", name="uq_parent_student_link"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    relationship: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[LinkStatus] = mapped_column(
        Enum(LinkStatus, name="parent_link_status"), default=LinkStatus.PENDING, nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    approved_at: Mapped[datetime | None] = mapped_column()
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class LinkInviteCode(Base):
    """Teacher-generated one-time code a parent enters to link instantly (no
    separate approval step -- generating the code IS the teacher's approval).
    """

    __tablename__ = "link_invite_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class SyllabusProgress(Base):
    __tablename__ = "syllabus_progress"
    __table_args__ = (
        UniqueConstraint("batch_id", "subject_id", "topic_id", name="uq_syllabus_progress_topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False, index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("topics.id"), nullable=False, index=True)
    status: Mapped[SyllabusStatus] = mapped_column(
        Enum(SyllabusStatus, name="syllabus_status"), default=SyllabusStatus.NOT_STARTED, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column()
    marked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class Remark(Base):
    __tablename__ = "remarks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("batches.id"), nullable=False, index=True)
    remark_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RemarkCategory] = mapped_column(
        Enum(RemarkCategory, name="remark_category"), default=RemarkCategory.GENERAL, nullable=False
    )
    visible_to_parent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
