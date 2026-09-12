"""PDF-to-Assessment pipeline (product spec section 13).

PDF -> validate -> store -> background job -> extract text (OCR fallback for
scanned PDFs) -> AI segmentation into structured questions -> the SAME
validate_generated_question_set() gate as question generation -> DRAFT
assessment for teacher review. Never auto-published.

Runs as a FastAPI BackgroundTask, not Celery/RQ -- see docs/ai-pipeline.md for
why (same reason as Phase 4's analytics recalculation: Docker/Redis aren't
available to actually test a real broker in this environment). The triggering
endpoint still returns immediately with a job id; the teacher polls
GET /ai/jobs/{id} for status, matching the spec's requirement either way.
"""

import io
import uuid
from datetime import datetime, timezone

import app.ai as ai_module
import app.db.session as db_session_module
from app.models.ai_job import AIExtractionJob, ExtractionJobStatus
from app.models.assessment import Assessment, AssessmentStatus, Question, QuestionOption
from app.models.subject import Subject, Topic
from app.schemas.ai import AIGeneratedQuestionSet
from app.services.ai_validation import AIValidationError, validate_generated_question_set
from app.storage import get_storage

MIN_EXTRACTABLE_CHARS = 20  # below this, pypdf likely got nothing useful -> try OCR
TOOL_NAME = "return_extracted_questions"


class AIPipelineError(Exception):
    pass


def _extract_text_pypdf(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_with_ocr_fallback(pdf_bytes: bytes) -> str:
    text = _extract_text_pypdf(pdf_bytes)
    if len(text.strip()) >= MIN_EXTRACTABLE_CHARS:
        return text

    # ponytail: real OCR path, but pytesseract/pdf2image (plus the Tesseract and
    # Poppler system binaries they wrap) aren't installed in this environment,
    # so this degrades to a clear, honest error rather than crashing or silently
    # returning empty text. Upgrade path: pip install pytesseract pdf2image and
    # install the Tesseract + Poppler binaries -- no other code changes needed.
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError as e:
        raise AIPipelineError(
            "This PDF appears to be scanned/image-based (little to no extractable text) "
            "and OCR support is not installed in this environment."
        ) from e

    images = convert_from_bytes(pdf_bytes)
    return "\n".join(pytesseract.image_to_string(image) for image in images)


def _build_extraction_prompt(text: str, subject_name: str, topic_names: list[str]) -> str:
    topics_line = f"Known topics for this subject: {', '.join(topic_names)}.\n" if topic_names else ""
    return (
        "You are extracting exam questions from a document a teacher uploaded. Below is the "
        "raw extracted text of the document, which may include a separate answer key section "
        "near the end. Segment it into individual questions, extract their options where "
        "present, and use any answer key section to determine which options are correct.\n\n"
        f"Subject: {subject_name}\n"
        f"{topics_line}"
        "For each question, set topic_name to the closest matching known topic if one clearly "
        "applies, or omit it if none does. Estimate a difficulty (EASY/MEDIUM/HARD) and a "
        "reasonable marks value for each question based on its complexity.\n\n"
        "Rules (same as always): MCQ needs exactly one correct option; MULTI_SELECT needs at "
        "least one; TRUE_FALSE needs exactly two options with exactly one correct; NUMERICAL "
        "needs exactly one option holding the correct numeric answer; SHORT_ANSWER/LONG_ANSWER "
        "must have no options. Never invent questions that aren't in the document.\n\n"
        "--- DOCUMENT TEXT ---\n"
        f"{text[:15000]}"
    )


def create_extraction_job(db, teacher, batch, subject, file_name: str, pdf_bytes: bytes) -> AIExtractionJob:
    storage_key = f"ai-extract-{uuid.uuid4().hex}.pdf"
    get_storage().save(pdf_bytes, storage_key)

    job = AIExtractionJob(
        teacher_id=teacher.id,
        batch_id=batch.id,
        subject_id=subject.id,
        file_name=file_name,
        storage_key=storage_key,
        status=ExtractionJobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_extraction_job(job_id: uuid.UUID) -> None:
    """BackgroundTask entry point. Opens its own DB session -- looked up via the
    module (not imported by name) so tests can point it at their isolated test
    engine, same pattern as analytics_service.recalculate_after_attempt.
    """
    db = db_session_module.SessionLocal()
    try:
        job = db.get(AIExtractionJob, job_id)
        if job is None:
            return

        job.status = ExtractionJobStatus.PROCESSING
        db.commit()

        try:
            pdf_bytes = get_storage().read(job.storage_key)
            text = _extract_text_with_ocr_fallback(pdf_bytes)

            subject = db.get(Subject, job.subject_id)
            topics = db.query(Topic).filter(Topic.subject_id == job.subject_id).all()

            prompt = _build_extraction_prompt(text, subject.name, [t.name for t in topics])
            provider = ai_module.get_ai_provider()
            raw = provider.generate_structured(prompt, AIGeneratedQuestionSet.model_json_schema(), TOOL_NAME)
            questions = validate_generated_question_set(raw)

            total_marks = sum(q.marks for q in questions)
            assessment = Assessment(
                teacher_id=job.teacher_id,
                batch_id=job.batch_id,
                subject_id=job.subject_id,
                title=f"Extracted from {job.file_name}",
                duration_minutes=max(10, len(questions) * 3),
                total_marks=total_marks,
                status=AssessmentStatus.DRAFT,
            )
            db.add(assessment)
            db.flush()

            topics_by_name = {t.name.lower(): t.id for t in topics}
            for i, q in enumerate(questions):
                topic_id = topics_by_name.get((q.topic_name or "").lower())
                question = Question(
                    assessment_id=assessment.id,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    topic_id=topic_id,
                    difficulty=q.difficulty,
                    marks=q.marks,
                    order_index=i,
                    source="AI_EXTRACTED",
                )
                db.add(question)
                db.flush()
                for j, opt in enumerate(q.options):
                    db.add(
                        QuestionOption(
                            question_id=question.id, option_text=opt.option_text, is_correct=opt.is_correct, order_index=j
                        )
                    )

            job.status = ExtractionJobStatus.COMPLETED
            job.assessment_id = assessment.id
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

        except AIValidationError as e:
            db.rollback()
            job = db.get(AIExtractionJob, job_id)
            job.status = ExtractionJobStatus.FAILED
            job.error_message = "; ".join(e.errors)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:  # noqa: BLE001 -- background job: must never crash silently
            db.rollback()
            job = db.get(AIExtractionJob, job_id)
            job.status = ExtractionJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
