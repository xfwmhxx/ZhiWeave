from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from celery import Celery
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from studyrag_backend.api.dependencies import DatabaseSession, get_knowledge_base, request_settings
from studyrag_backend.models.enums import IngestionTaskStatus
from studyrag_backend.models.ingestion_task import IngestionTask
from studyrag_backend.schemas.ingestion import IngestionTaskRead
from studyrag_backend.services.task_queue import (
    TERMINAL_TASK_STATUSES,
    TaskQueueUnavailable,
    TaskQuotaExceeded,
    create_and_enqueue_task,
)
from studyrag_backend.workers.celery_app import celery_app

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/tasks", tags=["tasks"])


async def _task(session: DatabaseSession, knowledge_base_id: UUID, task_id: UUID) -> IngestionTask:
    task = await session.get(IngestionTask, task_id)
    if task is None or task.knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=list[IngestionTaskRead])
async def list_tasks(
    knowledge_base_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[IngestionTask]:
    await get_knowledge_base(session, knowledge_base_id)
    result = await session.scalars(
        select(IngestionTask)
        .where(IngestionTask.knowledge_base_id == knowledge_base_id)
        .order_by(IngestionTask.created_at.desc())
        .limit(limit)
    )
    return list(result)


@router.post("/{task_id}/cancel", response_model=IngestionTaskRead)
async def cancel_task(
    knowledge_base_id: UUID,
    task_id: UUID,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id, allow_deleting=True)
    task = await _task(session, knowledge_base_id, task_id)
    if task.status in TERMINAL_TASK_STATUSES:
        return task
    task.cancel_requested = True
    task.pause_requested = False
    if task.status == IngestionTaskStatus.PENDING:
        task.status = IngestionTaskStatus.CANCELLED
        task.current_stage = "排队期间取消"
        task.finished_at = datetime.now(UTC)
        if task.celery_task_id:
            cast(Celery, celery_app).control.revoke(task.celery_task_id, terminate=False)
    else:
        task.current_stage = "等待安全取消点"
    await session.commit()
    await session.refresh(task)
    return task


@router.post("/{task_id}/pause", response_model=IngestionTaskRead)
async def pause_task(
    knowledge_base_id: UUID, task_id: UUID, session: DatabaseSession
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id, allow_deleting=True)
    task = await _task(session, knowledge_base_id, task_id)
    if task.status in TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=409, detail="terminal tasks cannot be paused")
    task.pause_requested = True
    task.current_stage = "等待安全暂停点"
    await session.commit()
    await session.refresh(task)
    return task


@router.post("/{task_id}/resume", response_model=IngestionTaskRead)
async def resume_task(
    knowledge_base_id: UUID, task_id: UUID, session: DatabaseSession
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id, allow_deleting=True)
    task = await _task(session, knowledge_base_id, task_id)
    if not task.pause_requested and task.status != IngestionTaskStatus.PAUSED:
        raise HTTPException(status_code=409, detail="task is not paused")
    task.pause_requested = False
    task.status = IngestionTaskStatus.RETRYING
    task.current_stage = "正在恢复"
    await session.commit()
    await session.refresh(task)
    return task


@router.post(
    "/{task_id}/retry",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_task(
    knowledge_base_id: UUID,
    task_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id, allow_deleting=True)
    task = await _task(session, knowledge_base_id, task_id)
    if task.status not in {
        IngestionTaskStatus.FAILED,
        IngestionTaskStatus.CANCELLED,
        IngestionTaskStatus.PARTIALLY_COMPLETED,
    }:
        raise HTTPException(status_code=409, detail="only failed or cancelled tasks can be retried")
    try:
        return await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            document_id=task.document_id,
            task_type=task.task_type,
            payload=dict(task.payload),
            retry_of_task_id=task.id,
        )
    except TaskQuotaExceeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskQueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
