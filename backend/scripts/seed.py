"""Seed the database with realistic demo data: 2 teachers, 3 batches, ~15 students,
and a couple of homework assignments in pending/submitted/late states.

Run with: python -m scripts.seed
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.analytics import Attendance, AttendanceStatus
from app.models.assessment import (
    Assessment,
    AssessmentAttempt,
    AssessmentStatus,
    AttemptStatus,
    Question,
    QuestionOption,
    QuestionType,
    Response,
    ResponseSelectedOption,
)
from app.models.batch import Batch, BatchStudent
from app.models.homework import Homework, HomeworkSubmission, SubmissionStatus
from app.models.subject import Subject, Topic
from app.models.user import User, UserRole

TEACHERS = [
    {"name": "Priya Nair", "email": "priya.nair@tutoros.dev"},
    {"name": "Vikram Rao", "email": "vikram.rao@tutoros.dev"},
]

BATCHES = [
    {"teacher": 0, "name": "Class 10-A Mathematics", "grade": "10", "section": "A", "academic_year": "2025-26"},
    {"teacher": 0, "name": "Class 9-B Mathematics", "grade": "9", "section": "B", "academic_year": "2025-26"},
    {"teacher": 1, "name": "Class 10-A Science", "grade": "10", "section": "A", "academic_year": "2025-26"},
]

STUDENT_NAMES = [
    "Rahul Sharma", "Ananya Gupta", "Aryan Verma", "Ishita Singh", "Kabir Malhotra",
    "Sneha Reddy", "Arjun Mehta", "Diya Kapoor", "Vivaan Joshi", "Myra Iyer",
    "Aditya Kumar", "Saanvi Pillai", "Reyansh Chatterjee", "Anika Desai", "Kian Bhatt",
]


def _fake_submission(homework_id, student_id, submitted_at, status) -> HomeworkSubmission:
    return HomeworkSubmission(
        homework_id=homework_id,
        student_id=student_id,
        submitted_at=submitted_at,
        status=status,
        file_name="submission.pdf",
        storage_key=f"seed-{homework_id}-{student_id}.pdf",
        mime_type="application/pdf",
        file_size=12345,
    )


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == TEACHERS[0]["email"]).first():
            print("Seed data already present, skipping.")
            return

        teacher_users = []
        for t in TEACHERS:
            user = User(
                name=t["name"],
                email=t["email"],
                password_hash=hash_password("password123"),
                role=UserRole.TEACHER,
            )
            db.add(user)
            teacher_users.append(user)
        db.flush()

        batches = []
        for b in BATCHES:
            batch = Batch(
                teacher_id=teacher_users[b["teacher"]].id,
                name=b["name"],
                grade=b["grade"],
                section=b["section"],
                academic_year=b["academic_year"],
            )
            db.add(batch)
            batches.append(batch)
        db.flush()

        students_by_batch: dict = {b.id: [] for b in batches}
        for i, name in enumerate(STUDENT_NAMES):
            email = f"{name.lower().replace(' ', '.')}@tutoros.dev"
            student = User(
                name=name,
                email=email,
                password_hash=hash_password("password123"),
                role=UserRole.STUDENT,
            )
            db.add(student)
            db.flush()
            # Spread students across the 3 batches.
            batch = batches[i % len(batches)]
            db.add(BatchStudent(batch_id=batch.id, student_id=student.id))
            students_by_batch[batch.id].append(student)

        subject = Subject(name="Mathematics", grade="10")
        db.add(subject)
        db.flush()

        topics = {
            name: Topic(subject_id=subject.id, name=name)
            for name in ["Algebra", "Geometry", "Trigonometry"]
        }
        for t in topics.values():
            db.add(t)
        db.flush()

        now = datetime.now(timezone.utc)
        batch_0_students = students_by_batch[batches[0].id]

        upcoming_homework = Homework(
            teacher_id=teacher_users[0].id,
            batch_id=batches[0].id,
            subject_id=subject.id,
            title="Algebra Worksheet 1",
            description="Solve all 20 problems in Chapter 3.",
            due_date=now + timedelta(days=3),
        )
        db.add(upcoming_homework)
        db.flush()
        # First two students submitted on time; the rest are left pending.
        for student in batch_0_students[:2]:
            db.add(_fake_submission(upcoming_homework.id, student.id, now, SubmissionStatus.SUBMITTED))

        closed_homework = Homework(
            teacher_id=teacher_users[0].id,
            batch_id=batches[0].id,
            subject_id=subject.id,
            title="Geometry Basics Quiz Prep",
            description="Review chapter 5 before the quiz.",
            due_date=now - timedelta(days=2),
            allow_late_submissions=True,
        )
        db.add(closed_homework)
        db.flush()
        # One submitted before the deadline, one submitted late after the teacher reopened it,
        # the remaining students never submitted (still "pending" in the roster).
        db.add(
            _fake_submission(
                closed_homework.id, batch_0_students[0].id, now - timedelta(days=3), SubmissionStatus.SUBMITTED
            )
        )
        db.add(
            _fake_submission(
                closed_homework.id, batch_0_students[1].id, now - timedelta(hours=6), SubmissionStatus.LATE
            )
        )

        # --- A published assessment with one question of every type, plus one
        # completed attempt so the "results" view has something real to show. ---
        assessment = Assessment(
            teacher_id=teacher_users[0].id,
            batch_id=batches[0].id,
            subject_id=subject.id,
            title="Algebra & Geometry Quiz",
            description="Covers Chapters 3-5. Answer every question.",
            duration_minutes=20,
            total_marks=10,
            status=AssessmentStatus.PUBLISHED,
        )
        db.add(assessment)
        db.flush()

        def add_question(question_type, text, marks, options, topic=None):
            q = Question(
                assessment_id=assessment.id, question_text=text, question_type=question_type, marks=marks,
                topic_id=topic.id if topic else None,
            )
            db.add(q)
            db.flush()
            option_rows = []
            for i, (text_, correct) in enumerate(options):
                opt = QuestionOption(question_id=q.id, option_text=text_, is_correct=correct, order_index=i)
                db.add(opt)
                db.flush()
                option_rows.append(opt)
            return q, option_rows

        mcq, mcq_opts = add_question(
            QuestionType.MCQ, "What is the value of x in 2x + 3 = 11?", 2, [("3", False), ("4", True)], topics["Algebra"]
        )
        multi, multi_opts = add_question(
            QuestionType.MULTI_SELECT,
            "Which of these are prime numbers?",
            3,
            [("2", True), ("4", False), ("7", True)],
            topics["Algebra"],
        )
        tf, tf_opts = add_question(
            QuestionType.TRUE_FALSE, "The sum of angles in a triangle is 180 degrees.", 1,
            [("True", True), ("False", False)], topics["Geometry"],
        )
        numerical, numerical_opts = add_question(
            QuestionType.NUMERICAL, "What is the value of pi rounded to the nearest whole number?", 2,
            [("3", True)], topics["Geometry"],
        )
        short, _short_opts = add_question(
            QuestionType.SHORT_ANSWER, "Explain the Pythagorean theorem in one sentence.", 2, [], topics["Geometry"]
        )

        # One student completes the whole test correctly (except the manually-graded short answer).
        scorer = batch_0_students[2]
        attempt = AssessmentAttempt(
            assessment_id=assessment.id,
            student_id=scorer.id,
            started_at=now - timedelta(minutes=15),
            submitted_at=now - timedelta(minutes=2),
            status=AttemptStatus.SUBMITTED,
            total_score=8,  # 2 + 3 + 1 + 2, short answer left ungraded
        )
        db.add(attempt)
        db.flush()

        def add_response(question, marks, is_correct, selected_option_ids=None, response_text=None):
            score = None if is_correct is None else (marks if is_correct else 0.0)
            r = Response(
                attempt_id=attempt.id,
                question_id=question.id,
                response_text=response_text,
                score=score,
                is_correct=is_correct,
            )
            db.add(r)
            db.flush()
            for oid in selected_option_ids or []:
                db.add(ResponseSelectedOption(response_id=r.id, option_id=oid))

        add_response(mcq, 2, True, selected_option_ids=[mcq_opts[1].id])
        add_response(multi, 3, True, selected_option_ids=[multi_opts[0].id, multi_opts[2].id])
        add_response(tf, 1, True, selected_option_ids=[tf_opts[0].id])
        add_response(numerical, 2, True, response_text="3")
        add_response(short, 2, None, response_text="It relates the sides of a right triangle: a^2+b^2=c^2.")

        # --- Four short practice quizzes over time, each covering all three topics,
        # so mastery/trend has enough history to be meaningful for the Attention
        # Panel and class-performance charts (needs >3 attempts per topic to get a
        # real recent-vs-historical split rather than "insufficient data"). ---
        rahul, ishita, arjun = batch_0_students[0], batch_0_students[1], batch_0_students[2]
        # out of 2 marks per topic per round; ratios tell the trend story:
        STUDENT_ROUND_SCORES = {
            rahul.id: {"Trigonometry": [1, 1, 2, 2], "Algebra": [2, 2, 2, 2], "Geometry": [2, 1, 1, 0]},
            ishita.id: {"Trigonometry": [2, 1, 1, 0], "Algebra": [0, 1, 1, 2], "Geometry": [1, 1, 1, 1]},
            arjun.id: {"Trigonometry": [2, 2, 2, 2], "Algebra": [2, 2, 2, 2], "Geometry": [2, 2, 2, 2]},
        }
        topic_names = ["Algebra", "Geometry", "Trigonometry"]

        for round_index in range(4):
            round_assessment = Assessment(
                teacher_id=teacher_users[0].id,
                batch_id=batches[0].id,
                subject_id=subject.id,
                title=f"Practice Quiz {round_index + 1}",
                duration_minutes=15,
                total_marks=2 * len(topic_names),
                status=AssessmentStatus.PUBLISHED,
            )
            db.add(round_assessment)
            db.flush()

            round_questions = {}
            for topic_name in topic_names:
                q = Question(
                    assessment_id=round_assessment.id,
                    question_text=f"{topic_name} question {round_index + 1}",
                    question_type=QuestionType.SHORT_ANSWER,
                    topic_id=topics[topic_name].id,
                    marks=2,
                )
                db.add(q)
                db.flush()
                round_questions[topic_name] = q

            submitted_at = now - timedelta(days=(4 - round_index) * 6)
            for student_id, topic_scores in STUDENT_ROUND_SCORES.items():
                round_total = sum(topic_scores[t][round_index] for t in topic_names)
                round_attempt = AssessmentAttempt(
                    assessment_id=round_assessment.id,
                    student_id=student_id,
                    started_at=submitted_at - timedelta(minutes=15),
                    submitted_at=submitted_at,
                    status=AttemptStatus.SUBMITTED,
                    total_score=round_total,
                )
                db.add(round_attempt)
                db.flush()
                for topic_name in topic_names:
                    score = topic_scores[topic_name][round_index]
                    db.add(
                        Response(
                            attempt_id=round_attempt.id,
                            question_id=round_questions[topic_name].id,
                            response_text=str(score),
                            score=score,
                            is_correct=score >= 2,
                        )
                    )

        # --- Attendance: last 10 days for every student in batch 0, with a
        # realistic present/absent/late mix (not just 100% for everyone). ---
        attendance_pattern = {
            0: [AttendanceStatus.PRESENT] * 9 + [AttendanceStatus.ABSENT],  # ~90%
            1: [AttendanceStatus.PRESENT] * 6 + [AttendanceStatus.ABSENT] * 3 + [AttendanceStatus.LATE],  # ~70%
            2: [AttendanceStatus.PRESENT] * 8 + [AttendanceStatus.LATE, AttendanceStatus.ABSENT],  # ~90%
            3: [AttendanceStatus.PRESENT] * 10,  # 100%
            4: [AttendanceStatus.PRESENT] * 5 + [AttendanceStatus.ABSENT] * 5,  # ~50%
        }
        for i, student in enumerate(batch_0_students):
            pattern = attendance_pattern.get(i, [AttendanceStatus.PRESENT] * 10)
            for day_offset, status_value in enumerate(pattern):
                db.add(
                    Attendance(
                        batch_id=batches[0].id,
                        student_id=student.id,
                        date=(now - timedelta(days=len(pattern) - day_offset)).date(),
                        status=status_value,
                    )
                )

        db.commit()
        print(f"Seeded {len(teacher_users)} teachers, {len(batches)} batches, {len(STUDENT_NAMES)} students.")
        print("Seeded 2 homework assignments with submitted/pending/late states.")
        print("Seeded 1 published assessment (mixed question types) with 1 completed attempt awaiting grading.")
        print("Seeded 4 rounds of practice quizzes across 3 topics for 3 students (varied mastery/trend) plus 10 days of attendance.")
        print("All accounts use password: password123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
