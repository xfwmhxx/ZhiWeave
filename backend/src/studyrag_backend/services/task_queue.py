from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from celery import Celery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from studyrag_backend.core.config import Settings
from studyrag_backend.models.enums import IngestionTaskStatus, IngestionTaskType
from studyrag_backend.models.ingestion_task import IngestionTask
from studyrag_backend.workers.celery_app import celery_app

TERMINAL_TASK_STATUSES = (
    IngestionTaskStatus.COMPLETED,
    IngestionTaskStatus.FAILED,
    IngestionTaskStatus.CANCELLED,
    IngestionTaskStatus.PARTIALLY_COMPLETED,
)


class TaskQueueUnavailable(RuntimeError):
    pass


class TaskQuotaExceeded(RuntimeError):
    pass


async def create_and_enqueue_task(
    session: AsyncSession,
    settings: Settings,
    *,
    knowledge_base_id: UUID,
    task_type: IngestionTaskType,
    payload: dict[str, object],
    document_id: UUID | None = None,
    retry_of_task_id: UUID | None = None,
    enforce_quota: bool = True,
) -> IngestionTask:
    if enforce_quota:
        active_count = await session.scalar(
            select(func.count(IngestionTask.id)).where(
                IngestionTask.knowledge_base_id == knowledge_base_id,
                IngestionTask.status.not_in(TERMINAL_TASK_STATUSES),
            )
        )
        if (active_count or 0) >= settings.max_active_tasks_per_knowledge_base:
            raise TaskQuotaExceeded("too many active tasks for this knowledge base")

    task = IngestionTask(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        task_type=task_type,
        status=IngestionTaskStatus.PENDING,
        progress=0,
        current_stage="等待 Worker",
        payload=payload,
        retry_of_task_id=retry_of_task_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    app = cast(Celery, celery_app)
    try:
        queued = app.send_task("studyrag.ingestion.execute", args=[str(task.id)], queue="ingestion")
    except Exception as exc:
        task.status = IngestionTaskStatus.FAILED
        task.current_stage = "任务提交失败"
        task.error_code = "broker_unavailable"
        task.error_message = str(exc)[:1000]
        task.finished_at = datetime.now(UTC)
        await session.commit()
        raise TaskQueueUnavailable("the ingestion worker queue is unavailable") from exc
    task.celery_task_id = queued.id
    await session.commit()
    await session.refresh(task)
    return task
