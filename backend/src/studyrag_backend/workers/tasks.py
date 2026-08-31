import asyncio
from typing import Any
from uuid import UUID

from studyrag_backend.core.config import get_settings
from studyrag_backend.services.ingestion import execute_ingestion_task
from studyrag_backend.workers.celery_app import celery_app


@celery_app.task(name="studyrag.system.ping")  # type: ignore[untyped-decorator]
def system_ping() -> dict[str, Any]:
    """A real broker/worker smoke-test task used during setup and monitoring."""
    return {"status": "ok", "worker": "celery"}


@celery_app.task(name="studyrag.ingestion.execute")  # type: ignore[untyped-decorator]
def execute_ingestion(task_id: str) -> dict[str, int | str]:
    """Dispatch one persisted, idempotent knowledge-base operation."""
    return asyncio.run(execute_ingestion_task(UUID(task_id), get_settings()))


# Keep the original task name compatible with already queued development tasks.
@celery_app.task(name="studyrag.ingestion.web")  # type: ignore[untyped-decorator]
def ingest_web(task_id: str) -> dict[str, int | str]:
    return asyncio.run(execute_ingestion_task(UUID(task_id), get_settings()))
