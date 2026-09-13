"""Parent-child linking (privacy-critical) and the parent progress dashboard.

Verification-flow decision (see docs/PROGRESS.md Phase 8 for the full writeup):
two linking paths, both ending at the same `parent_student_links` row --

1. Invite code: a teacher generates a one-time code scoped to one student
   (`LinkInviteCode.created_by` is always a teacher, per the schema). A parent
   entering a still-valid, unused code is auto-approved immediately -- the act
   of generating and handing over that code IS the teacher's approval, so a
   second approval step would be pure friction with no added safety.
2. Pending request: a parent who doesn't have a code submits the student's
   email; this creates a PENDING row and a teacher who actually teaches that
   student must explicitly approve or reject it (`GET/POST /teachers/link-requests`).

In both cases, `get_approved_link` is the single choke point every child-data
read goes through -- a PENDING or REJECTED link is never sufficient, and an
unrelated parent gets a 404 (never a 403) so a request can't be used to probe
whether a given student id/email exists.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assessment import Assessment, AssessmentAttempt, AttemptStatus
from app.models.batch import Batch, BatchStudent, BatchStudentStatus
from app.models.parent import LinkInviteCode, LinkStatus, ParentStudentLink, Remark, SyllabusProgress, SyllabusStatus
from app.models.profile import StudentProfile
from app.models.subject import Subject, Topic
from app.models.user import User, UserRole
from app.schemas.analytics import StudentPerformanceRead
from app.schemas.parent import (
    ChildProgressRead,
    ChildRead,
    RecentTestResult,
    RemarkRead,
    SyllabusSubjectProgress,
)
from app.services import analytics_service, student_service

LINK_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link request not found")
CHILD_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
INVALID_CODE = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite code")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Invite codes (teacher-generated)
# ---------------------------------------------------------------------------


def generate_invite_code(db: Session, teacher: User, student_id: uuid.UUID) -> LinkInviteCode:
    # Raises 404 if this teacher doesn't actually teach this student -- reuses
    # the same ownership join every other teacher-scoped student lookup uses.
    student_service.get_student_for_teacher(db, teacher, student_id)

    code = secrets.token_hex(4).upper()  # 8 hex chars, short enough for a parent to type
    invite = LinkInviteCode(
        student_id=student_id,
        code=code,
        created_by=teacher.id,
        expires_at=_now() + timedelta(hours=settings.link_invite_code_expiry_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def redeem_invite_code(db: Session, parent: User, code: str, relationship: str | None) -> ParentStudentLink:
    invite = db.query(LinkInviteCode).filter(LinkInviteCode.code == code.strip().upper()).first()
    if invite is None or invite.used_at is not None or _aware(invite.expires_at) < _now():
        raise INVALID_CODE

    link = _upsert_link(db, parent, invite.student_id, relationship, auto_approve_by=invite.created_by)
    invite.used_at = _now()
    db.commit()
    db.refresh(link)
    return link


# ---------------------------------------------------------------------------
# Pending requests (no code)
# ---------------------------------------------------------------------------


def request_link_by_email(
    db: Session, parent: User, student_email: str, relationship: str | None
) -> ParentStudentLink:
    student = db.query(User).filter(User.email == student_email, User.role == UserRole.STUDENT).first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return _upsert_link(db, parent, student.id, relationship, auto_approve_by=None)


def _upsert_link(
    db: Session,
    parent: User,
    student_id: uuid.UUID,
    relationship: str | None,
    auto_approve_by: uuid.UUID | None,
) -> ParentStudentLink:
    existing = (
        db.query(ParentStudentLink)
        .filter(ParentStudentLink.parent_id == parent.id, ParentStudentLink.student_id == student_id)
        .first()
    )

    if existing is not None and existing.status in (LinkStatus.PENDING, LinkStatus.APPROVED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A link request already exists for this child")

    link = existing or ParentStudentLink(parent_id=parent.id, student_id=student_id)
    link.relationship = relationship
    link.requested_at = _now()
    link.approved_at = None
    link.approved_by = None

    if auto_approve_by is not None:
        link.status = LinkStatus.APPROVED
        link.approved_at = _now()
        link.approved_by = auto_approve_by
    else:
        link.status = LinkStatus.PENDING

    if existing is None:
        db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ---------------------------------------------------------------------------
# Teacher-side approval
# ---------------------------------------------------------------------------


def _teacher_can_act_on(db: Session, teacher: User, student_id: uuid.UUID) -> bool:
    return (
        db.query(BatchStudent)
        .join(Batch, Batch.id == BatchStudent.batch_id)
        .filter(
            Batch.teacher_id == teacher.id,
            BatchStudent.student_id == student_id,
            BatchStudent.status == BatchStudentStatus.ACTIVE,
        )
        .first()
        is not None
    )


def list_pending_requests_for_teacher(db: Session, teacher: User) -> list[dict]:
    rows = (
        db.query(ParentStudentLink, User)
        .join(User, User.id == ParentStudentLink.parent_id)
        .filter(ParentStudentLink.status == LinkStatus.PENDING)
        .order_by(ParentStudentLink.requested_at)
        .all()
    )
    result = []
    for link, parent in rows:
        if not _teacher_can_act_on(db, teacher, link.student_id):
            continue
        student = db.get(User, link.student_id)
        result.append(
            {
                "id": link.id,
                "parent_name": parent.name,
                "parent_email": parent.email,
                "student_id": link.student_id,
                "student_name": student.name if student else "Unknown",
                "relationship": link.relationship,
                "requested_at": link.requested_at,
            }
        )
    return result


def _get_pending_link_for_teacher(db: Session, teacher: User, link_id: uuid.UUID) -> ParentStudentLink:
    link = db.get(ParentStudentLink, link_id)
    if link is None or not _teacher_can_act_on(db, teacher, link.student_id):
        raise LINK_NOT_FOUND
    if link.status != LinkStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request was already handled")
    return link


def approve_link(db: Session, teacher: User, link_id: uuid.UUID) -> ParentStudentLink:
    link = _get_pending_link_for_teacher(db, teacher, link_id)
    link.status = LinkStatus.APPROVED
    link.approved_at = _now()
    link.approved_by = teacher.id
    db.commit()
    db.refresh(link)
    return link


def reject_link(db: Session, teacher: User, link_id: uuid.UUID) -> ParentStudentLink:
    link = _get_pending_link_for_teacher(db, teacher, link_id)
    link.status = LinkStatus.REJECTED
    db.commit()
    db.refresh(link)
    return link


# ---------------------------------------------------------------------------
# Parent-side reads -- everything below is gated on an APPROVED link
# ---------------------------------------------------------------------------


def get_approved_link(db: Session, parent: User, student_id: uuid.UUID) -> ParentStudentLink:
    link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == LinkStatus.APPROVED,
        )
        .first()
    )
    if link is None:
        raise CHILD_NOT_FOUND
    return link


def list_children(db: Session, parent: User) -> list[ChildRead]:
    rows = (
        db.query(ParentStudentLink, User)
        .join(User, User.id == ParentStudentLink.student_id)
        .filter(ParentStudentLink.parent_id == parent.id, ParentStudentLink.status == LinkStatus.APPROVED)
        .order_by(User.name)
        .all()
    )
    result = []
    for link, student in rows:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
        result.append(
            ChildRead(
                student_id=student.id,
                name=student.name,
                email=student.email,
                grade=profile.grade if profile else None,
                relationship=link.relationship,
                linked_since=link.approved_at,
            )
        )
    return result


def _syllabus_for_student(db: Session, student_id: uuid.UUID) -> list[SyllabusSubjectProgress]:
    batch_ids = [
        row[0]
        for row in db.query(BatchStudent.batch_id)
        .filter(BatchStudent.student_id == student_id, BatchStudent.status == BatchStudentStatus.ACTIVE)
        .all()
    ]
    if not batch_ids:
        return []

    subject_ids = {
        row[0]
        for row in db.query(SyllabusProgress.subject_id)
        .filter(SyllabusProgress.batch_id.in_(batch_ids))
        .distinct()
        .all()
    }

    result = []
    for subject_id in subject_ids:
        subject = db.get(Subject, subject_id)
        if subject is None:
            continue
        total_topics = db.query(Topic).filter(Topic.subject_id == subject_id).count()
        completed = (
            db.query(SyllabusProgress)
            .filter(
                SyllabusProgress.batch_id.in_(batch_ids),
                SyllabusProgress.subject_id == subject_id,
                SyllabusProgress.status == SyllabusStatus.COMPLETED,
            )
            .count()
        )
        percentage = round(completed / total_topics * 100, 2) if total_topics else 0.0
        result.append(
            SyllabusSubjectProgress(
                subject_id=subject_id,
                subject_name=subject.name,
                total_topics=total_topics,
                completed_topics=completed,
                percentage=percentage,
            )
        )
    return result


def _recent_tests_for_student(db: Session, student_id: uuid.UUID, limit: int = 10) -> list[RecentTestResult]:
    rows = (
        db.query(AssessmentAttempt, Assessment)
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .filter(
            AssessmentAttempt.student_id == student_id,
            AssessmentAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED]),
        )
        .order_by(AssessmentAttempt.submitted_at.desc())
        .limit(limit)
        .all()
    )
    return [
        RecentTestResult(
            assessment_id=a.id,
            title=a.title,
            total_marks=a.total_marks,
            score=att.total_score,
            submitted_at=att.submitted_at,
        )
        for att, a in rows
    ]


def _remarks_for_student(db: Session, student_id: uuid.UUID, limit: int = 20) -> list[RemarkRead]:
    rows = (
        db.query(Remark, User)
        .join(User, User.id == Remark.teacher_id)
        .filter(Remark.student_id == student_id, Remark.visible_to_parent.is_(True))
        .order_by(Remark.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        RemarkRead(
            id=r.id,
            teacher_name=t.name,
            batch_id=r.batch_id,
            remark_text=r.remark_text,
            category=r.category,
            created_at=r.created_at,
        )
        for r, t in rows
    ]


def get_child_progress(db: Session, parent: User, student_id: uuid.UUID) -> ChildProgressRead:
    get_approved_link(db, parent, student_id)  # the one authorization choke point

    student = db.get(User, student_id)
    if student is None:
        raise CHILD_NOT_FOUND

    performance = analytics_service.compute_student_performance(db, student_id)
    performance_read = StudentPerformanceRead.model_validate(performance, from_attributes=True)

    return ChildProgressRead(
        student_id=student_id,
        student_name=student.name,
        performance=performance_read,
        syllabus=_syllabus_for_student(db, student_id),
        recent_tests=_recent_tests_for_student(db, student_id),
        remarks=_remarks_for_student(db, student_id),
    )
