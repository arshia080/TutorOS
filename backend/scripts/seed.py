"""Seed the database with realistic demo data per product spec section 35:
3 teachers, 5 batches, 40 students, 2 subjects (6 topics), several homework
assignments, several assessments with hundreds of responses across all
students, attendance, and homework submissions -- so a fresh clone looks like
a live product immediately.

Run with: python -m scripts.seed
"""

import random
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
from app.models.parent import (
    LinkStatus,
    ParentProfile,
    ParentStudentLink,
    Remark,
    RemarkCategory,
    SyllabusProgress,
    SyllabusStatus,
)
from app.models.profile import TeacherProfile
from app.models.subject import Subject, Topic
from app.models.user import User, UserRole

RNG_SEED = 20260908  # deterministic across re-seeds, purely for reproducible demo data
TEACHERS = [
    {"name": "Priya Nair", "email": "priya.nair@tutoros.dev"},
    {"name": "Vikram Rao", "email": "vikram.rao@tutoros.dev"},
    {"name": "Meera Krishnan", "email": "meera.krishnan@tutoros.dev"},
]

# Batch 0 and 2 carry the hand-crafted "storyline" students (see STUDENT_ROUND_SCORES
# below) -- their subject determines which topic set the storyline quizzes use.
BATCHES = [
    {"teacher": 0, "name": "Class 10-A Mathematics", "grade": "10", "section": "A", "academic_year": "2025-26", "subject": "Mathematics"},
    {"teacher": 0, "name": "Class 9-B Mathematics", "grade": "9", "section": "B", "academic_year": "2025-26", "subject": "Mathematics"},
    {"teacher": 1, "name": "Class 10-A Science", "grade": "10", "section": "A", "academic_year": "2025-26", "subject": "Science"},
    {"teacher": 1, "name": "Class 9-A Science", "grade": "9", "section": "A", "academic_year": "2025-26", "subject": "Science"},
    {"teacher": 2, "name": "Class 10-B Mathematics", "grade": "10", "section": "B", "academic_year": "2025-26", "subject": "Mathematics"},
]

STUDENT_NAMES = [
    "Rahul Sharma", "Ananya Gupta", "Aryan Verma", "Ishita Singh", "Kabir Malhotra",
    "Sneha Reddy", "Arjun Mehta", "Diya Kapoor", "Vivaan Joshi", "Myra Iyer",
    "Aditya Kumar", "Saanvi Pillai", "Reyansh Chatterjee", "Anika Desai", "Kian Bhatt",
    "Advait Rao", "Riya Nair", "Vihaan Menon", "Kavya Iyengar", "Arnav Bose",
    "Zara Khan", "Ayaan Sheikh", "Ira Bhattacharya", "Dhruv Choudhary", "Navya Agarwal",
    "Yash Trivedi", "Prisha Bhavsar", "Rohan Kulkarni", "Aadhya Shetty", "Sai Patil",
    "Anaya Chauhan", "Vedant Saxena", "Kiara Mishra", "Shaurya Tiwari", "Aarohi Ghosh",
    "Reyaan Bakshi", "Amaira Sengupta", "Atharv Bedi", "Meher Kohli", "Vivan Thakur",
]

SUBJECT_TOPICS = {
    "Mathematics": ["Algebra", "Geometry", "Trigonometry"],
    "Science": ["Physics", "Chemistry", "Biology"],
}


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


def _bulk_quiz_rounds(db, rng, teacher_id, batch, subject, topics, students, rounds, now):
    """Generates `rounds` short assessments (one question per topic) attempted
    by every student in the batch, with pseudo-random-but-plausible scores.
    This is what gets the response count into the hundreds without hand-crafting
    every student's trajectory.
    """
    topic_names = list(topics.keys())
    response_count = 0
    for round_index in range(rounds):
        assessment = Assessment(
            teacher_id=teacher_id,
            batch_id=batch.id,
            subject_id=subject.id,
            title=f"{subject.name} Class Test {round_index + 1}",
            duration_minutes=20,
            total_marks=2 * len(topic_names),
            status=AssessmentStatus.PUBLISHED,
        )
        db.add(assessment)
        db.flush()

        round_questions = {}
        for topic_name in topic_names:
            q = Question(
                assessment_id=assessment.id,
                question_text=f"{topic_name} question (test {round_index + 1})",
                question_type=QuestionType.SHORT_ANSWER,
                topic_id=topics[topic_name].id,
                marks=2,
            )
            db.add(q)
            db.flush()
            round_questions[topic_name] = q

        submitted_at = now - timedelta(days=(rounds - round_index) * 5)
        for student in students:
            # Each student gets a stable per-student aptitude per topic (0..1)
            # that drifts slightly round to round, so trends emerge naturally
            # instead of being pure noise.
            scores = {}
            for topic_name in topic_names:
                base = rng.uniform(0.3, 0.95)
                drift = (round_index - rounds / 2) * rng.uniform(-0.05, 0.08)
                ratio = max(0.0, min(1.0, base + drift))
                scores[topic_name] = 2 if rng.random() < ratio else (1 if rng.random() < ratio else 0)

            attempt = AssessmentAttempt(
                assessment_id=assessment.id,
                student_id=student.id,
                started_at=submitted_at - timedelta(minutes=20),
                submitted_at=submitted_at,
                status=AttemptStatus.SUBMITTED,
                total_score=sum(scores.values()),
            )
            db.add(attempt)
            db.flush()
            for topic_name in topic_names:
                db.add(
                    Response(
                        attempt_id=attempt.id,
                        question_id=round_questions[topic_name].id,
                        response_text=str(scores[topic_name]),
                        score=scores[topic_name],
                        is_correct=scores[topic_name] >= 2,
                    )
                )
                response_count += 1
    return response_count


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    rng = random.Random(RNG_SEED)
    try:
        if db.query(User).filter(User.email == TEACHERS[0]["email"]).first():
            print("Seed data already present, skipping.")
            return

        teacher_users = []
        for t in TEACHERS:
            user = User(name=t["name"], email=t["email"], password_hash=hash_password("password123"), role=UserRole.TEACHER)
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

        # Spread all 40 students round-robin across the 5 batches (8 each).
        students_by_batch: dict = {b.id: [] for b in batches}
        all_students = []
        for i, name in enumerate(STUDENT_NAMES):
            email = f"{name.lower().replace(' ', '.')}@tutoros.dev"
            student = User(name=name, email=email, password_hash=hash_password("password123"), role=UserRole.STUDENT)
            db.add(student)
            db.flush()
            batch = batches[i % len(batches)]
            db.add(BatchStudent(batch_id=batch.id, student_id=student.id))
            students_by_batch[batch.id].append(student)
            all_students.append(student)

        subjects = {}
        topics_by_subject = {}
        for subject_name, topic_names in SUBJECT_TOPICS.items():
            subject = Subject(name=subject_name, grade="10")
            db.add(subject)
            db.flush()
            subjects[subject_name] = subject
            topic_map = {}
            for topic_name in topic_names:
                topic = Topic(subject_id=subject.id, name=topic_name)
                db.add(topic)
                db.flush()
                topic_map[topic_name] = topic
            topics_by_subject[subject_name] = topic_map

        now = datetime.now(timezone.utc)
        math_subject = subjects["Mathematics"]
        math_topics = topics_by_subject["Mathematics"]
        batch_0_students = students_by_batch[batches[0].id]

        # --- Homework: a couple of assignments for batch 0, with a realistic
        # submitted/pending/late spread across that batch's students. ---
        upcoming_homework = Homework(
            teacher_id=teacher_users[0].id, batch_id=batches[0].id, subject_id=math_subject.id,
            title="Algebra Worksheet 1", description="Solve all 20 problems in Chapter 3.",
            due_date=now + timedelta(days=3),
        )
        db.add(upcoming_homework)
        db.flush()
        for student in batch_0_students[: len(batch_0_students) // 2]:
            db.add(_fake_submission(upcoming_homework.id, student.id, now, SubmissionStatus.SUBMITTED))

        closed_homework = Homework(
            teacher_id=teacher_users[0].id, batch_id=batches[0].id, subject_id=math_subject.id,
            title="Geometry Basics Quiz Prep", description="Review chapter 5 before the quiz.",
            due_date=now - timedelta(days=2), allow_late_submissions=True,
        )
        db.add(closed_homework)
        db.flush()
        db.add(_fake_submission(closed_homework.id, batch_0_students[0].id, now - timedelta(days=3), SubmissionStatus.SUBMITTED))
        db.add(_fake_submission(closed_homework.id, batch_0_students[1].id, now - timedelta(hours=6), SubmissionStatus.LATE))
        for student in batch_0_students[2:5]:
            db.add(_fake_submission(closed_homework.id, student.id, now - timedelta(days=1), SubmissionStatus.SUBMITTED))

        # --- A published assessment with one question of every type, plus one
        # completed attempt so the "results" review view has something real to show. ---
        assessment = Assessment(
            teacher_id=teacher_users[0].id, batch_id=batches[0].id, subject_id=math_subject.id,
            title="Algebra & Geometry Quiz", description="Covers Chapters 3-5. Answer every question.",
            duration_minutes=20, total_marks=10, status=AssessmentStatus.PUBLISHED,
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

        mcq, mcq_opts = add_question(QuestionType.MCQ, "What is the value of x in 2x + 3 = 11?", 2, [("3", False), ("4", True)], math_topics["Algebra"])
        multi, multi_opts = add_question(QuestionType.MULTI_SELECT, "Which of these are prime numbers?", 3, [("2", True), ("4", False), ("7", True)], math_topics["Algebra"])
        tf, tf_opts = add_question(QuestionType.TRUE_FALSE, "The sum of angles in a triangle is 180 degrees.", 1, [("True", True), ("False", False)], math_topics["Geometry"])
        numerical, numerical_opts = add_question(QuestionType.NUMERICAL, "What is the value of pi rounded to the nearest whole number?", 2, [("3", True)], math_topics["Geometry"])
        short, _short_opts = add_question(QuestionType.SHORT_ANSWER, "Explain the Pythagorean theorem in one sentence.", 2, [], math_topics["Geometry"])

        scorer = batch_0_students[2]
        attempt = AssessmentAttempt(
            assessment_id=assessment.id, student_id=scorer.id,
            started_at=now - timedelta(minutes=15), submitted_at=now - timedelta(minutes=2),
            status=AttemptStatus.SUBMITTED, total_score=8,
        )
        db.add(attempt)
        db.flush()

        def add_response(question, marks, is_correct, selected_option_ids=None, response_text=None):
            score = None if is_correct is None else (marks if is_correct else 0.0)
            r = Response(attempt_id=attempt.id, question_id=question.id, response_text=response_text, score=score, is_correct=is_correct)
            db.add(r)
            db.flush()
            for oid in selected_option_ids or []:
                db.add(ResponseSelectedOption(response_id=r.id, option_id=oid))

        add_response(mcq, 2, True, selected_option_ids=[mcq_opts[1].id])
        add_response(multi, 3, True, selected_option_ids=[multi_opts[0].id, multi_opts[2].id])
        add_response(tf, 1, True, selected_option_ids=[tf_opts[0].id])
        add_response(numerical, 2, True, response_text="3")
        add_response(short, 2, None, response_text="It relates the sides of a right triangle: a^2+b^2=c^2.")

        # --- Hand-crafted storyline: three named students with deliberately
        # different mastery trajectories (mastered/stable, declining, improving)
        # so the Attention Panel and class charts show real narrative variety,
        # not just noise. Everyone else in the batch gets the randomized bulk
        # generation below instead. ---
        rahul, ishita, arjun = batch_0_students[0], batch_0_students[1], batch_0_students[2]
        STUDENT_ROUND_SCORES = {
            rahul.id: {"Trigonometry": [1, 1, 2, 2], "Algebra": [2, 2, 2, 2], "Geometry": [2, 1, 1, 0]},
            ishita.id: {"Trigonometry": [2, 1, 1, 0], "Algebra": [0, 1, 1, 2], "Geometry": [1, 1, 1, 1]},
            arjun.id: {"Trigonometry": [2, 2, 2, 2], "Algebra": [2, 2, 2, 2], "Geometry": [2, 2, 2, 2]},
        }
        topic_names = ["Algebra", "Geometry", "Trigonometry"]
        for round_index in range(4):
            round_assessment = Assessment(
                teacher_id=teacher_users[0].id, batch_id=batches[0].id, subject_id=math_subject.id,
                title=f"Practice Quiz {round_index + 1}", duration_minutes=15,
                total_marks=2 * len(topic_names), status=AssessmentStatus.PUBLISHED,
            )
            db.add(round_assessment)
            db.flush()
            round_questions = {}
            for topic_name in topic_names:
                q = Question(
                    assessment_id=round_assessment.id, question_text=f"{topic_name} question {round_index + 1}",
                    question_type=QuestionType.SHORT_ANSWER, topic_id=math_topics[topic_name].id, marks=2,
                )
                db.add(q)
                db.flush()
                round_questions[topic_name] = q
            submitted_at = now - timedelta(days=(4 - round_index) * 6)
            for student_id, topic_scores in STUDENT_ROUND_SCORES.items():
                round_total = sum(topic_scores[t][round_index] for t in topic_names)
                round_attempt = AssessmentAttempt(
                    assessment_id=round_assessment.id, student_id=student_id,
                    started_at=submitted_at - timedelta(minutes=15), submitted_at=submitted_at,
                    status=AttemptStatus.SUBMITTED, total_score=round_total,
                )
                db.add(round_attempt)
                db.flush()
                for topic_name in topic_names:
                    score = topic_scores[topic_name][round_index]
                    db.add(
                        Response(
                            attempt_id=round_attempt.id, question_id=round_questions[topic_name].id,
                            response_text=str(score), score=score, is_correct=score >= 2,
                        )
                    )

        # --- Bulk-generate class tests across every batch (all its students,
        # skipping the 3 storyline students already handled above for batch 0)
        # so the total response count reaches the hundreds, per spec section 35. ---
        total_responses = 0
        storyline_ids = {rahul.id, ishita.id, arjun.id}
        for b, batch_config in zip(batches, BATCHES):
            subject = subjects[batch_config["subject"]]
            topics = topics_by_subject[batch_config["subject"]]
            students = [s for s in students_by_batch[b.id] if s.id not in storyline_ids]
            total_responses += _bulk_quiz_rounds(db, rng, b.teacher_id, b, subject, topics, students, rounds=4, now=now)

        # --- Attendance: last 15 days for every student in every batch, with a
        # varied present/absent/late mix per student (not just 100% for everyone). ---
        for student in all_students:
            present_rate = rng.uniform(0.55, 1.0)
            for day_offset in range(15):
                roll = rng.random()
                if roll < present_rate * 0.9:
                    status_value = AttendanceStatus.PRESENT
                elif roll < present_rate:
                    status_value = AttendanceStatus.LATE
                else:
                    status_value = AttendanceStatus.ABSENT
                batch_id = next(bid for bid, students in students_by_batch.items() if student in students)
                db.add(
                    Attendance(
                        batch_id=batch_id, student_id=student.id,
                        date=(now - timedelta(days=15 - day_offset)).date(), status=status_value,
                    )
                )

        # --- Phase 8: Parent Portal demo data ---------------------------------
        # Teacher-discoverable profile for the primary teacher (search-by-locality demo).
        db.add(
            TeacherProfile(
                user_id=teacher_users[0].id,
                institute_name="Nair Learning Center",
                bio="15 years teaching CBSE Mathematics, specializing in board-exam prep.",
                locality="Andheri West",
                city="Mumbai",
                pincode="400058",
            )
        )

        # Syllabus progress for batch 0 / Mathematics: a realistic mixed state
        # (some chapters done, one in progress, one untouched) for the
        # syllabus-percentage demo in both the teacher checklist and parent view.
        db.add(SyllabusProgress(batch_id=batches[0].id, subject_id=math_subject.id, topic_id=math_topics["Algebra"].id, status=SyllabusStatus.COMPLETED, completed_at=now - timedelta(days=20), marked_by=teacher_users[0].id))
        db.add(SyllabusProgress(batch_id=batches[0].id, subject_id=math_subject.id, topic_id=math_topics["Geometry"].id, status=SyllabusStatus.COMPLETED, completed_at=now - timedelta(days=8), marked_by=teacher_users[0].id))
        db.add(SyllabusProgress(batch_id=batches[0].id, subject_id=math_subject.id, topic_id=math_topics["Trigonometry"].id, status=SyllabusStatus.IN_PROGRESS, marked_by=teacher_users[0].id, notes="Started basic identities this week."))

        # Remarks on Rahul (storyline student) -- one parent-visible, one not,
        # to demonstrate the visibility filter in both dashboards.
        db.add(Remark(student_id=rahul.id, teacher_id=teacher_users[0].id, batch_id=batches[0].id, remark_text="Consistently strong in Algebra; keep up the practice pace.", category=RemarkCategory.ACADEMIC, visible_to_parent=True, created_at=now - timedelta(days=5)))
        db.add(Remark(student_id=rahul.id, teacher_id=teacher_users[0].id, batch_id=batches[0].id, remark_text="Needs to focus more during Geometry sessions -- talks out of turn.", category=RemarkCategory.BEHAVIOR, visible_to_parent=True, created_at=now - timedelta(days=2)))
        db.add(Remark(student_id=rahul.id, teacher_id=teacher_users[0].id, batch_id=batches[0].id, remark_text="Internal note: flagged for scholarship review, don't mention to family yet.", category=RemarkCategory.GENERAL, visible_to_parent=False, created_at=now - timedelta(days=1)))

        # Two parents: one fully approved (via invite code, demonstrating the
        # instant-link flow) linked to Rahul, one still PENDING on Ishita so the
        # teacher's Link Requests panel has something to act on out of the box.
        parent_rahul = User(name="Sunita Sharma", email="sunita.sharma@tutoros.dev", password_hash=hash_password("password123"), role=UserRole.PARENT)
        db.add(parent_rahul)
        db.flush()
        db.add(ParentProfile(user_id=parent_rahul.id, phone="+91-98765-43210", locality="Andheri West"))
        db.add(
            ParentStudentLink(
                parent_id=parent_rahul.id, student_id=rahul.id, relationship="Mother",
                status=LinkStatus.APPROVED, requested_at=now - timedelta(days=10),
                approved_at=now - timedelta(days=10), approved_by=teacher_users[0].id,
            )
        )

        parent_ishita = User(name="Rajesh Singh", email="rajesh.singh@tutoros.dev", password_hash=hash_password("password123"), role=UserRole.PARENT)
        db.add(parent_ishita)
        db.flush()
        db.add(ParentProfile(user_id=parent_ishita.id, phone="+91-98765-11111", locality="Andheri West"))
        db.add(
            ParentStudentLink(
                parent_id=parent_ishita.id, student_id=ishita.id, relationship="Father",
                status=LinkStatus.PENDING, requested_at=now - timedelta(hours=6),
            )
        )

        db.commit()
        print(f"Seeded {len(teacher_users)} teachers, {len(batches)} batches, {len(STUDENT_NAMES)} students.")
        print(f"Seeded 2 subjects (Mathematics, Science), {sum(len(t) for t in topics_by_subject.values())} topics.")
        print("Seeded 2 homework assignments with submitted/pending/late states.")
        print("Seeded 1 mixed-question-type assessment plus 4 rounds of hand-crafted storyline quizzes.")
        print(f"Seeded {total_responses}+ additional randomized class-test responses across all batches (hundreds total).")
        print("Seeded 15 days of attendance for every student.")
        print("Seeded Phase 8 parent portal data: 1 teacher profile (searchable), syllabus progress for 3 topics,")
        print(f"3 remarks (1 hidden from parents), 1 approved parent link (Sunita Sharma -> Rahul), 1 pending link (Rajesh Singh -> {ishita.name}).")
        print("All accounts use password: password123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
