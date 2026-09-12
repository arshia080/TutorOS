"""Real Celery/RQ-backed background jobs (product spec section 6/28), now that
this environment has a working Redis to build and test against.

Previously (Phases 0-7) this project's background jobs ran via FastAPI's
`BackgroundTasks` because no Docker/Redis was available to build or test a
real broker against -- see docs/PROGRESS.md and docs/architecture.md for that
history. The swap was exactly as narrow as those docs promised: each job was
already a single function taking JSON-serializable arguments and opening its
own DB session; becoming a Celery task means wrapping it with `@celery_app.task`
and changing the call site from `background_tasks.add_task(fn, ...)` to
`fn.delay(...)`. No service-layer logic changed.

Run a worker with:
    celery -A app.celery_app worker --loglevel=info --pool=solo
(--pool=solo is required on Windows; drop it on Linux/Mac for the default
 prefork pool.)
"""

import uuid

from celery import Celery

from app.core.config import settings

celery_app = Celery("tutoros", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Tests set this to True (see tests/conftest.py) so `.delay()` runs the task
    # synchronously in-process instead of requiring a real broker/worker --
    # the standard Celery testing pattern.
    task_always_eager=False,
)


@celery_app.task(name="ai.process_extraction_job")
def process_extraction_job_task(job_id: str) -> None:
    from app.services.ai_pdf_service import process_extraction_job

    process_extraction_job(uuid.UUID(job_id))


@celery_app.task(name="analytics.recalculate_after_attempt")
def recalculate_after_attempt_task(student_id: str, topic_ids: list[str]) -> None:
    from app.services.analytics_service import recalculate_after_attempt

    recalculate_after_attempt(uuid.UUID(student_id), [uuid.UUID(t) for t in topic_ids])
