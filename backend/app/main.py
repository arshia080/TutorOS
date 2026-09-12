from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    assessments,
    attendance,
    auth,
    batches,
    health,
    homework,
    students,
    subjects,
    teachers,
)
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="TutorOS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(assessments.router)
app.include_router(attendance.router)
app.include_router(batches.router)
app.include_router(homework.router)
app.include_router(students.router)
app.include_router(subjects.router)
app.include_router(teachers.router)
