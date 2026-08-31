from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from studyrag_backend.api.dependencies import DatabaseSession, get_knowledge_base, request_settings
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.document_revision import DocumentRevision
from studyrag_backend.models.enums import (
    DocumentSourceType,
    DocumentStatus,
    IngestionTaskType,
    VectorSyncStatus,
)
from studyrag_backend.models.ingestion_task import IngestionTask
from studyrag_backend.schemas.ingestion import (
    ChunkContextRead,
    ChunkRead,
    DocumentRead,
    DocumentRevisionRead,
    DocumentUpdate,
    IngestionTaskRead,
)
from studyrag_backend.services.task_queue import (
    TaskQueueUnavailable,
    TaskQuotaExceeded,
    create_and_enqueue_task,
)

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}", tags=["documents"])


async def _document(
    session: DatabaseSession, knowledge_base_id: UUID, document_id: UUID
) -> Document:
    document = await session.get(Document, document_id)
    if document is None or document.knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


async def _queue(
    request: Request,
    session: DatabaseSession,
    *,
    knowledge_base_id: UUID,
    task_type: IngestionTaskType,
    payload: dict[str, object],
    document_id: UUID,
) -> IngestionTask:
    try:
        return await create_and_enqueue_task(
            session,
            request_settings(request),
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            task_type=task_type,
            payload=payload,
        )
    except TaskQuotaExceeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskQueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/documents", response_model=list[DocumentRead])
async def list_documents(
    knowledge_base_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Document]:
    await get_knowledge_base(session, knowledge_base_id)
    result = await session.scalars(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    knowledge_base_id: UUID, document_id: UUID, session: DatabaseSession
) -> Document:
    await get_knowledge_base(session, knowledge_base_id)
    return await _document(session, knowledge_base_id, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    payload: DocumentUpdate,
    request: Request,
    session: DatabaseSession,
) -> Document:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    document = await _document(session, knowledge_base_id, document_id)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        if field == "title" and isinstance(value, str):
            value = value.strip()
        setattr(document, field, value)
    document.vector_sync_status = VectorSyncStatus.PENDING
    await session.commit()
    qdrant = cast(QdrantManager, request.app.state.qdrant)
    try:
        await qdrant.vector_store.update_document_payload(
            knowledge_base.vector_collection_name,
            document.id,
            {
                "title": document.title,
                "language": document.language,
                "source_type": document.source_type.value,
            },
        )
    except Exception as exc:
        document.vector_sync_status = VectorSyncStatus.ERROR
        document.vector_sync_error = str(exc)[:1000]
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail="metadata was saved, but vector payload synchronization failed; run repair",
        ) from exc
    document.vector_sync_status = VectorSyncStatus.SYNCED
    document.vector_sync_error = None
    await session.commit()
    await session.refresh(document)
    return document


@router.delete(
    "/documents/{document_id}",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    document = await _document(session, knowledge_base_id, document_id)
    task = await _queue(
        request,
        session,
        knowledge_base_id=knowledge_base_id,
        task_type=IngestionTaskType.DELETE_DOCUMENT,
        payload={"kind": "delete_document", "document_id": str(document_id)},
        document_id=document_id,
    )
    document.status = DocumentStatus.DELETING
    await session.commit()
    return task


@router.post(
    "/documents/{document_id}/reindex",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    await _document(session, knowledge_base_id, document_id)
    return await _queue(
        request,
        session,
        knowledge_base_id=knowledge_base_id,
        task_type=IngestionTaskType.REINDEX_DOCUMENT,
        payload={"kind": "reindex_document", "document_id": str(document_id)},
        document_id=document_id,
    )


@router.post(
    "/documents/{document_id}/refetch",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refetch_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    document = await _document(session, knowledge_base_id, document_id)
    if document.source_type != DocumentSourceType.WEB_PAGE or not document.source_uri:
        return await _queue(
            request,
            session,
            knowledge_base_id=knowledge_base_id,
            task_type=IngestionTaskType.REINDEX_DOCUMENT,
            payload={"kind": "reindex_document", "document_id": str(document_id)},
            document_id=document_id,
        )
    return await _queue(
        request,
        session,
        knowledge_base_id=knowledge_base_id,
        task_type=IngestionTaskType.INGEST_DOCUMENT,
        payload={"kind": "web", "seed_url": document.source_uri, "max_pages": 1},
        document_id=document_id,
    )


@router.get("/documents/{document_id}/versions", response_model=list[DocumentRevisionRead])
async def list_document_versions(
    knowledge_base_id: UUID, document_id: UUID, session: DatabaseSession
) -> list[DocumentRevision]:
    await get_knowledge_base(session, knowledge_base_id)
    await _document(session, knowledge_base_id, document_id)
    result = await session.scalars(
        select(DocumentRevision)
        .where(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
    )
    return list(result)


@router.post("/documents/{document_id}/disable", response_model=DocumentRead)
async def disable_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> Document:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    document = await _document(session, knowledge_base_id, document_id)
    qdrant = cast(QdrantManager, request.app.state.qdrant)
    await qdrant.vector_store.delete_document_points(
        knowledge_base.vector_collection_name, document_id
    )
    document.enabled = False
    document.vector_sync_status = VectorSyncStatus.SYNCED
    document.vector_sync_error = None
    await session.commit()
    await session.refresh(document)
    return document


@router.post(
    "/documents/{document_id}/enable",
    response_model=IngestionTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enable_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> IngestionTask:
    await get_knowledge_base(session, knowledge_base_id)
    document = await _document(session, knowledge_base_id, document_id)
    task = await _queue(
        request,
        session,
        knowledge_base_id=knowledge_base_id,
        task_type=IngestionTaskType.REINDEX_DOCUMENT,
        payload={"kind": "reindex_document", "document_id": str(document_id)},
        document_id=document_id,
    )
    document.enabled = True
    document.vector_sync_status = VectorSyncStatus.PENDING
    await session.commit()
    return task


@router.get("/chunks", response_model=list[ChunkRead])
async def list_chunks(
    knowledge_base_id: UUID,
    session: DatabaseSession,
    document_id: UUID | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Chunk]:
    await get_knowledge_base(session, knowledge_base_id)
    statement = (
        select(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.knowledge_base_id == knowledge_base_id)
    )
    if document_id:
        statement = statement.where(Chunk.document_id == document_id)
    if search:
        statement = statement.where(Chunk.content.ilike(f"%{search}%"))
    result = await session.scalars(
        statement.order_by(Document.created_at.desc(), Chunk.sequence_index)
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/chunks/{chunk_id}/context", response_model=ChunkContextRead)
async def read_chunk_context(
    knowledge_base_id: UUID,
    chunk_id: UUID,
    session: DatabaseSession,
) -> ChunkContextRead:
    await get_knowledge_base(session, knowledge_base_id)
    row = (
        await session.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Chunk.id == chunk_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    chunk, document = row
    neighbors = list(
        await session.scalars(
            select(Chunk).where(
                Chunk.document_id == chunk.document_id,
                Chunk.sequence_index.in_([chunk.sequence_index - 1, chunk.sequence_index + 1]),
            )
        )
    )
    by_sequence = {neighbor.sequence_index: neighbor for neighbor in neighbors}
    return ChunkContextRead(
        chunk=ChunkRead.model_validate(chunk),
        previous_chunk=(
            ChunkRead.model_validate(by_sequence[chunk.sequence_index - 1])
            if chunk.sequence_index - 1 in by_sequence
            else None
        ),
        next_chunk=(
            ChunkRead.model_validate(by_sequence[chunk.sequence_index + 1])
            if chunk.sequence_index + 1 in by_sequence
            else None
        ),
        title=document.title,
        source_uri=document.source_uri,
    )
