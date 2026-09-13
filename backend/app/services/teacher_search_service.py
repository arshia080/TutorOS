"""Teacher discovery for parents. Deliberately public-shaped: never touches
batches, assessments, or student data as anything other than a source for
the *aggregate* "which subjects/grades does this teacher teach" facts --
no student-identifying information is ever returned.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.batch import Batch
from app.models.profile import TeacherProfile
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.parent import TeacherProfileUpdate, TeacherSearchResult


def get_own_profile(db: Session, teacher: User) -> TeacherProfile | None:
    return db.query(TeacherProfile).filter(TeacherProfile.user_id == teacher.id).first()


def upsert_teacher_profile(db: Session, teacher: User, data: TeacherProfileUpdate) -> TeacherProfile:
    profile = get_own_profile(db, teacher)
    if profile is None:
        profile = TeacherProfile(user_id=teacher.id)
        db.add(profile)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


def _subjects_taught(db: Session, teacher_id: uuid.UUID) -> list[str]:
    rows = (
        db.query(Subject.name)
        .join(Assessment, Assessment.subject_id == Subject.id)
        .filter(Assessment.teacher_id == teacher_id)
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows})


def _grades_taught(db: Session, teacher_id: uuid.UUID) -> list[str]:
    rows = (
        db.query(Batch.grade)
        .filter(Batch.teacher_id == teacher_id, Batch.grade.isnot(None))
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows})


def search_teachers(
    db: Session,
    locality: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
) -> list[TeacherSearchResult]:
    query = (
        db.query(User, TeacherProfile)
        .join(TeacherProfile, TeacherProfile.user_id == User.id)
        .filter(User.role == UserRole.TEACHER)
    )

    if locality:
        pattern = f"%{locality.lower()}%"
        query = query.filter(
            (TeacherProfile.locality.ilike(pattern)) | (TeacherProfile.city.ilike(pattern))
        )

    results = []
    for teacher, profile in query.order_by(User.name).all():
        subjects = _subjects_taught(db, teacher.id)
        grades = _grades_taught(db, teacher.id)

        if subject and subject.lower() not in {s.lower() for s in subjects}:
            continue
        if grade and grade not in grades:
            continue

        results.append(
            TeacherSearchResult(
                teacher_id=teacher.id,
                name=teacher.name,
                institute_name=profile.institute_name,
                bio=profile.bio,
                locality=profile.locality,
                city=profile.city,
                subjects=subjects,
                grades=grades,
            )
        )
    return results
