import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

import app.ai as ai_module
from app.ai.base import AIProvider, AIProviderError
from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.ai_job import AIExtractionJob
from app.models.batch import Batch
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.ai import GenerateQuestionsRequest, PDFExtractionJobRead, StudentInsightRead
from app.schemas.assessment import AssessmentRead
from app.services import ai_insight_service, ai_pdf_service, ai_question_service, analytics_service
from app.services import student_service

router = APIRouter(prefix="/ai", tags=["ai"])
require_teacher = require_role(UserRole.TEACHER)

MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024


def get_provider() -> AIProvider:
    return ai_module.get_ai_provider()


@router.post("/generate-questions", response_model=AssessmentRead, status_code=201)
def generate_questions(
    data: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    provider: AIProvider = Depends(get_provider),
) -> AssessmentRead:
    return ai_question_service.generate_questions(db, teacher, provider, data)


@router.post("/assessments/{assessment_id}/questions/{question_id}/regenerate", response_model=dict)
def regenerate_question(
    assessment_id: uuid.UUID,
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
    provider: AIProvider = Depends(get_provider),
) -> dict:
    from app.api.routes.assessments import _question_read

    question = ai_question_service.regenerate_question(db, teacher, provider, assessment_id, question_id)
    return _question_read(db, question, include_correct=True).model_dump(mode="json")


@router.post("/pdf-extract", response_model=PDFExtractionJobRead, status_code=202)
async def extract_pdf(
    background_tasks: BackgroundTasks,
    batch_id: uuid.UUID = Form(...),
    subject_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> PDFExtractionJobRead:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    batch = db.get(Batch, batch_id)
    if batch is None or batch.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if db.get(Subject, subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    job = ai_pdf_service.create_extraction_job(db, teacher, batch, db.get(Subject, subject_id), file.filename or "upload.pdf", content)
    background_tasks.add_task(ai_pdf_service.process_extraction_job, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=PDFExtractionJobRead)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> PDFExtractionJobRead:
    job = db.get(AIExtractionJob, job_id)
    if job is None or job.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/students/{student_id}/topics/{topic_id}/insight", response_model=StudentInsightRead)
def get_student_insight(
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: AIProvider = Depends(get_provider),
) -> StudentInsightRead:
    if current_user.role == UserRole.STUDENT:
        if current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        student = current_user
    elif current_user.role == UserRole.TEACHER:
        student = student_service.get_student_for_teacher(db, current_user, student_id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    perf = analytics_service.compute_topic_performance(db, student_id, topic_id)
    if perf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No performance data for this topic yet")

    try:
        insight = ai_insight_service.generate_topic_insight(provider, perf, student.name)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    return StudentInsightRead(insight=insight)
