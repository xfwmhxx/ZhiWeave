from celery import Celery

from studyrag_backend.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "studyrag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["studyrag_backend.workers.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_default_queue="default",
    task_routes={
        "studyrag.ingestion.*": {"queue": "ingestion"},
        "studyrag.embedding.*": {"queue": "embedding"},
        "studyrag.export.*": {"queue": "export"},
    },
)
