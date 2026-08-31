import asyncio
from collections.abc import Iterator
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Annotated, BinaryIO, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from studyrag_backend.api.dependencies import DatabaseSession, get_knowledge_base, request_settings
from studyrag_backend.core.workspace import current_workspace
from studyrag_backend.infrastructure.embedding import EmbeddingRegistry
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.enums import IngestionTaskType, KnowledgeBaseStatus
from studyrag_backend.models.ingestion_task import IngestionTask
from studyrag_backend.models.knowledge_base import KnowledgeBase
from studyrag_backend.schemas.ingestion import ConsistencyReport, IngestionTaskRead, WebImportCreate
from studyrag_backend.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseReindex,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdate,
)
from studyrag_backend.services.consistency import inspect_consistency
from studyrag_backend.services.document_parser import SUPPORTED_UPLOAD_TYPES
from studyrag_backend.services.exporter import write_portable_export
from studyrag_backend.services.task_queue import (
    TERMINAL_TASK_STATUSES,
    TaskQueueUnavailable,
    TaskQuotaExceeded,
    create_and_enqueue_task,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


async def _to_summary(
    session: DatabaseSession, knowledge_base: KnowledgeBase
) -> KnowledgeBaseSummary:
    document_count = await session.scalar(
        select(func.count(Document.id)).where(Document.knowledge_base_id == knowledge_base.id)
    )
    chunk_count = await session.scalar(
        select(func.count(Chunk.id))
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.knowledge_base_id == knowledge_base.id)
    )
    active_task_count = await session.scalar(
        select(func.count(IngestionTask.id)).where(
            IngestionTask.knowledge_base_id == knowledge_base.id,
            IngestionTask.status.not_in(TERMINAL_TASK_STATUSES),
        )
    )
    return KnowledgeBaseSummary.model_validate(knowledge_base).model_copy(
        update={
            "document_count": document_count or 0,
            "chunk_count": chunk_count or 0,
            "active_task_count": active_task_count or 0,
        }
    )


def _task_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskQuotaExceeded):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, TaskQueueUnavailable):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("", response_model=KnowledgeBaseSummary, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    request: Request,
    session: DatabaseSession,
) -> KnowledgeBaseSummary:
    settings = request_settings(request)
    chunk_size = payload.chunk_size or settings.chunk_size
    chunk_overlap = (
        payload.chunk_overlap if payload.chunk_overlap is not None else settings.chunk_overlap
    )
    chunk_strategy = payload.chunk_strategy or settings.chunk_strategy
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="chunk_overlap must be smaller than chunk_size",
        )
    registry = cast(EmbeddingRegistry, request.app.state.embedding_registry)
    embedding = registry.get(
        model_name=settings.embedding_model_name,
        revision=settings.embedding_model_revision,
        dimension=settings.embedding_dimension,
        query_prefix=settings.embedding_query_prefix,
        passage_prefix=settings.embedding_passage_prefix,
    )
    knowledge_base_id = uuid4()
    knowledge_base = KnowledgeBase(
        id=knowledge_base_id,
        name=payload.name.strip(),
        workspace_id=current_workspace(),
        description=payload.description,
        embedding_model=settings.embedding_model_name,
        embedding_revision=settings.embedding_model_revision,
        embedding_dimension=settings.embedding_dimension,
        embedding_query_prefix=settings.embedding_query_prefix,
        embedding_passage_prefix=settings.embedding_passage_prefix,
        embedding_signature=embedding.signature,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_strategy=chunk_strategy,
        vector_collection_name=f"studyrag_{knowledge_base_id.hex}",
    )
    session.add(knowledge_base)
    await session.commit()
    await session.refresh(knowledge_base)
    return await _to_summary(session, knowledge_base)


@router.get("", response_model=list[KnowledgeBaseSummary])
async def list_knowledge_bases(session: DatabaseSession) -> list[KnowledgeBaseSummary]:
    result = await session.scalars(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.status != KnowledgeBaseStatus.DELETING,
            KnowledgeBase.workspace_id == current_workspace(),
        )
        .order_by(KnowledgeBase.created_at.desc())
    )
    return [await _to_summary(session, item) for item in result]


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseSummary)
async def read_knowledge_base(
    knowledge_base_id: UUID, session: DatabaseSession
) -> KnowledgeBaseSummary:
    return await _to_summary(session, await get_knowledge_base(session, knowledge_base_id))


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseSummary)
async def update_knowledge_base(
    knowledge_base_id: UUID,
    payload: KnowledgeBaseUpdate,
    session: DatabaseSession,
) -> KnowledgeBaseSummary:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") in {KnowledgeBaseStatus.DELETING, KnowledgeBaseStatus.FAILED}:
        raise HTTPException(status_code=422, detail="status is managed by the system")
    for field, value in values.items():
        if field == "name" and isinstance(value, str):
            value = value.strip()
        setattr(knowledge_base, field, value)
    if knowledge_base.semantic_weight + knowledge_base.keyword_weight <= 0:
        raise HTTPException(status_code=422, detail="retrieval weights must have a positive sum")
    await session.commit()
    await session.refresh(knowledge_base)
    return await _to_summary(session, knowledge_base)


@router.delete(
    "/{knowledge_base_id}", response_model=IngestionTaskRead, status_code=status.HTTP_202_ACCEPTED
)
async def delete_knowledge_base(
    knowledge_base_id: UUID, request: Request, session: DatabaseSession
) -> IngestionTask:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    try:
        task = await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.DELETE_KNOWLEDGE_BASE,
            payload={"kind": "delete_knowledge_base"},
        )
    except (TaskQuotaExceeded, TaskQueueUnavailable) as exc:
        raise _task_error(exc) from exc
    knowledge_base.status = KnowledgeBaseStatus.DELETING
    await session.commit()
    return task


@router.post(
    "/{knowledge_base_id}/imports/web",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_web_pages(
    knowledge_base_id: UUID,
    payload: WebImportCreate,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    try:
        return await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.INGEST_DOCUMENT,
            payload={
                "kind": "web",
                "seed_url": str(payload.seed_url),
                "max_pages": payload.max_pages,
            },
        )
    except (TaskQuotaExceeded, TaskQueueUnavailable) as exc:
        raise _task_error(exc) from exc


@router.post(
    "/{knowledge_base_id}/imports/files",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_file(
    knowledge_base_id: UUID,
    request: Request,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    settings = request_settings(request)
    original_name = Path(file.filename or "document.txt").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=415, detail="supported file types: .md, .markdown, .txt, .pdf"
        )
    upload_root = (settings.upload_dir / str(knowledge_base_id)).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    stored_path = (upload_root / f"{uuid4().hex}{suffix}").resolve()
    if upload_root not in stored_path.parents:
        raise HTTPException(status_code=400, detail="invalid upload path")
    size = 0
    try:
        with stored_path.open("xb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="uploaded file is too large")
                target.write(chunk)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    canonical_uri = f"upload://{knowledge_base_id}/{stored_path.stem}/{original_name}"
    try:
        return await create_and_enqueue_task(
            session,
            settings,
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.INGEST_DOCUMENT,
            payload={
                "kind": "file",
                "file_name": original_name,
                "mime_type": file.content_type or "application/octet-stream",
                "stored_path": str(stored_path),
                "canonical_uri": canonical_uri,
                "size": size,
            },
        )
    except (TaskQuotaExceeded, TaskQueueUnavailable) as exc:
        stored_path.unlink(missing_ok=True)
        raise _task_error(exc) from exc


@router.post(
    "/{knowledge_base_id}/reindex",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_knowledge_base(
    knowledge_base_id: UUID,
    payload: KnowledgeBaseReindex,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    configuration = payload.model_dump(exclude_none=True)
    chunk_size = int(configuration.get("chunk_size", knowledge_base.chunk_size))
    chunk_overlap = int(configuration.get("chunk_overlap", knowledge_base.chunk_overlap))
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="chunk_overlap must be smaller than chunk_size")
    try:
        return await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.REINDEX_KNOWLEDGE_BASE,
            payload={"kind": "reindex_knowledge_base", "configuration": configuration},
        )
    except (TaskQuotaExceeded, TaskQueueUnavailable) as exc:
        raise _task_error(exc) from exc


@router.get("/{knowledge_base_id}/consistency", response_model=ConsistencyReport)
async def check_consistency(
    knowledge_base_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> ConsistencyReport:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    registry = cast(EmbeddingRegistry, request.app.state.embedding_registry)
    embedding = registry.get(
        model_name=knowledge_base.embedding_model,
        revision=knowledge_base.embedding_revision,
        dimension=knowledge_base.embedding_dimension,
        query_prefix=knowledge_base.embedding_query_prefix,
        passage_prefix=knowledge_base.embedding_passage_prefix,
    )
    qdrant = cast(QdrantManager, request.app.state.qdrant)
    return await inspect_consistency(session, knowledge_base, qdrant, embedding)


@router.post(
    "/{knowledge_base_id}/consistency/repair",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def repair_consistency(
    knowledge_base_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    try:
        return await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.CONSISTENCY_REPAIR,
            payload={"kind": "consistency_repair", "configuration": {}},
        )
    except (TaskQuotaExceeded, TaskQueueUnavailable) as exc:
        raise _task_error(exc) from exc


@router.post("/{knowledge_base_id}/snapshots", status_code=status.HTTP_201_CREATED)
async def create_vector_snapshot(
    knowledge_base_id: UUID, request: Request, session: DatabaseSession
) -> dict[str, object]:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    qdrant = cast(QdrantManager, request.app.state.qdrant)
    snapshot = await qdrant.client.create_snapshot(knowledge_base.vector_collection_name)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="Qdrant did not create a snapshot")
    return {
        "name": snapshot.name,
        "size": snapshot.size,
        "created_at": snapshot.creation_time,
        "collection": knowledge_base.vector_collection_name,
    }


@router.get("/{knowledge_base_id}/snapshots")
async def list_vector_snapshots(
    knowledge_base_id: UUID, request: Request, session: DatabaseSession
) -> list[dict[str, object]]:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    qdrant = cast(QdrantManager, request.app.state.qdrant)
    snapshots = await qdrant.client.list_snapshots(knowledge_base.vector_collection_name)
    return [
        {"name": item.name, "size": item.size, "created_at": item.creation_time}
        for item in snapshots
    ]


@router.get("/{knowledge_base_id}/export")
async def export_knowledge_base(
    knowledge_base_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> StreamingResponse:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    documents = list(
        await session.scalars(
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at, Document.id)
        )
    )
    chunks = list(
        await session.scalars(
            select(Chunk)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at, Chunk.sequence_index)
        )
    )
    archive = SpooledTemporaryFile(  # noqa: SIM115 - closed by the stream generator
        max_size=request_settings(request).export_spool_bytes, mode="w+b"
    )
    await asyncio.to_thread(
        write_portable_export,
        cast(BinaryIO, archive),
        knowledge_base,
        documents,
        chunks,
    )
    archive.seek(0)

    def stream_archive() -> Iterator[bytes]:
        try:
            while data := archive.read(1024 * 1024):
                yield data
        finally:
            archive.close()

    filename = f"zhiweave-{knowledge_base_id}.zip"
    return StreamingResponse(
        stream_archive(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
