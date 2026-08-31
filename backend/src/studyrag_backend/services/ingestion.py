import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from studyrag_backend.core.config import Settings
from studyrag_backend.db.session import Database
from studyrag_backend.infrastructure.embedding import EmbeddingService
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.infrastructure.vector_store import VectorPoint
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.document_revision import DocumentRevision
from studyrag_backend.models.enums import (
    DocumentSourceType,
    DocumentStatus,
    IngestionTaskStatus,
    VectorSyncStatus,
)
from studyrag_backend.models.evaluation_case import RetrievalEvaluationCase
from studyrag_backend.models.ingestion_task import IngestionTask
from studyrag_backend.models.knowledge_base import KnowledgeBase
from studyrag_backend.services.chunking import ChunkDraft, split_text, split_text_by_tokens
from studyrag_backend.services.document_parser import SourceDocument, parse_uploaded_document
from studyrag_backend.services.upload_storage import (
    remove_knowledge_base_uploads,
    remove_uploaded_file,
)
from studyrag_backend.services.web_crawler import CrawledPage, WebCrawler

logger = logging.getLogger(__name__)


class TaskCancelled(RuntimeError):
    pass


@dataclass(slots=True)
class _EvaluationChunkTarget:
    case: RetrievalEvaluationCase
    document_id: UUID
    sequence_index: int
    content_hash: str


async def _detach_evaluation_chunk_targets(
    session: AsyncSession, document_ids: list[UUID]
) -> list[_EvaluationChunkTarget]:
    """Detach chunk FKs before replacement and retain a stable logical target."""
    if not document_ids:
        return []
    rows = await session.execute(
        select(RetrievalEvaluationCase, Chunk)
        .join(Chunk, RetrievalEvaluationCase.relevant_chunk_id == Chunk.id)
        .where(Chunk.document_id.in_(document_ids))
    )
    targets: list[_EvaluationChunkTarget] = []
    for case, chunk in rows.tuples():
        targets.append(
            _EvaluationChunkTarget(
                case=case,
                document_id=chunk.document_id,
                sequence_index=chunk.sequence_index,
                content_hash=chunk.content_hash,
            )
        )
        case.relevant_document_id = case.relevant_document_id or chunk.document_id
        case.relevant_chunk_id = None
    if targets:
        await session.flush()
    return targets


def _reattach_evaluation_chunk_targets(
    targets: list[_EvaluationChunkTarget], replacement_chunks: list[Chunk]
) -> None:
    chunk_ids = {
        (chunk.document_id, chunk.sequence_index, chunk.content_hash): chunk.id
        for chunk in replacement_chunks
    }
    for target in targets:
        target.case.relevant_chunk_id = chunk_ids.get(
            (target.document_id, target.sequence_index, target.content_hash)
        )


def embedding_for_configuration(
    settings: Settings,
    *,
    model_name: str,
    revision: str,
    dimension: int,
    query_prefix: str,
    passage_prefix: str,
) -> EmbeddingService:
    return EmbeddingService(
        model_name=model_name,
        revision=revision,
        dimension=dimension,
        query_prefix=query_prefix,
        passage_prefix=passage_prefix,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        cache_dir=settings.model_cache_dir,
    )


def embedding_for_knowledge_base(
    settings: Settings, knowledge_base: KnowledgeBase
) -> EmbeddingService:
    return embedding_for_configuration(
        settings,
        model_name=knowledge_base.embedding_model,
        revision=knowledge_base.embedding_revision,
        dimension=knowledge_base.embedding_dimension,
        query_prefix=knowledge_base.embedding_query_prefix,
        passage_prefix=knowledge_base.embedding_passage_prefix,
    )


async def _check_cancelled(session: AsyncSession, task: IngestionTask) -> None:
    await session.refresh(task, attribute_names=["cancel_requested", "pause_requested"])
    while task.pause_requested and not task.cancel_requested:
        task.status = IngestionTaskStatus.PAUSED
        task.current_stage = "任务已暂停"
        await session.commit()
        await asyncio.sleep(1)
        await session.refresh(task, attribute_names=["cancel_requested", "pause_requested"])
    if not task.cancel_requested:
        return
    task.status = IngestionTaskStatus.CANCELLED
    task.current_stage = "已按请求取消"
    task.finished_at = datetime.now(UTC)
    await session.commit()
    raise TaskCancelled(f"task {task.id} was cancelled")


async def _set_task_stage(
    session: AsyncSession,
    task: IngestionTask,
    *,
    status: IngestionTaskStatus,
    progress: int,
    stage: str,
) -> None:
    await _check_cancelled(session, task)
    task.status = status
    task.progress = progress
    task.current_stage = stage
    await session.commit()


def _source_from_page(page: CrawledPage) -> SourceDocument:
    return SourceDocument(
        title=page.title,
        content=page.content,
        source_type=DocumentSourceType.WEB_PAGE,
        source_uri=page.source_url,
        canonical_uri=page.canonical_url,
        language=page.language,
        mime_type="text/html",
        metadata={"crawler": "zhiweave", "source_kind": "web"},
    )


def _split_document(
    content: str,
    *,
    embedding: EmbeddingService,
    chunk_size: int,
    chunk_overlap: int,
    chunk_strategy: str,
) -> list[ChunkDraft]:
    if chunk_strategy == "token":
        return split_text_by_tokens(
            content,
            token_offsets=embedding.token_offsets(content),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return split_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _embedding_texts(source: SourceDocument, drafts: list[ChunkDraft]) -> list[str]:
    """Add document/section context for retrieval without polluting displayed Chunk text."""
    values: list[str] = []
    for draft in drafts:
        context = [source.title]
        if draft.section_heading and draft.section_heading != source.title:
            context.append(draft.section_heading)
        context.append(draft.content)
        values.append("\n".join(context))
    return values


def _chunk_rows_and_points(
    *,
    knowledge_base: KnowledgeBase,
    document_id: UUID,
    source: SourceDocument,
    drafts: list[ChunkDraft],
    vectors: list[list[float]],
    index_version: int | None = None,
    model_signature: str | None = None,
) -> tuple[list[Chunk], list[VectorPoint]]:
    chunks: list[Chunk] = []
    points: list[VectorPoint] = []
    resolved_version = index_version or knowledge_base.index_version
    resolved_signature = model_signature or knowledge_base.embedding_signature
    for draft, vector in zip(drafts, vectors, strict=True):
        chunk_id = uuid4()
        point_id = uuid5(
            NAMESPACE_URL,
            f"zhiweave:{document_id}:{draft.sequence_index}:{draft.content_hash}:"
            f"{resolved_signature}:{resolved_version}",
        )
        metadata = {
            "source_uri": source.source_uri,
            "title": source.title,
            "language": source.language,
            "source_type": source.source_type.value,
            "index_version": resolved_version,
            "enabled": True,
            "section_heading": draft.section_heading,
            "chunk_format": "structured-v2",
        }
        chunks.append(
            Chunk(
                id=chunk_id,
                document_id=document_id,
                sequence_index=draft.sequence_index,
                content=draft.content,
                content_hash=draft.content_hash,
                character_count=draft.character_count,
                token_count=draft.token_count,
                vector_point_id=point_id,
                start_offset=draft.start_offset,
                end_offset=draft.end_offset,
                extra_metadata=metadata,
            )
        )
        points.append(
            VectorPoint(
                id=point_id,
                vector=vector,
                payload={
                    "knowledge_base_id": str(knowledge_base.id),
                    "document_id": str(document_id),
                    "chunk_id": str(chunk_id),
                    "sequence_index": draft.sequence_index,
                    "content": draft.content,
                    "title": source.title,
                    "source_uri": source.source_uri,
                    "language": source.language,
                    "source_type": source.source_type.value,
                    "model_signature": resolved_signature,
                    "index_version": resolved_version,
                    "enabled": True,
                    "section_heading": draft.section_heading,
                    "chunk_format": "structured-v2",
                },
            )
        )
    return chunks, points


async def _index_source(
    *,
    session: AsyncSession,
    task: IngestionTask,
    knowledge_base: KnowledgeBase,
    source: SourceDocument,
    embedding: EmbeddingService,
    qdrant: QdrantManager,
    force: bool = False,
) -> tuple[Document, int]:
    content_hash = sha256(source.content.encode("utf-8")).hexdigest()
    document = await session.scalar(
        select(Document).where(
            Document.knowledge_base_id == knowledge_base.id,
            Document.canonical_uri == source.canonical_uri,
        )
    )
    if (
        not force
        and document is not None
        and document.content_hash == content_hash
        and document.status == DocumentStatus.READY
        and document.vector_sync_status == VectorSyncStatus.SYNCED
        and document.title == source.title
    ):
        return document, 0

    document_id = document.id if document else uuid4()
    old_point_ids = set(
        await session.scalars(select(Chunk.vector_point_id).where(Chunk.document_id == document_id))
    )
    drafts = _split_document(
        source.content,
        embedding=embedding,
        chunk_size=knowledge_base.chunk_size,
        chunk_overlap=knowledge_base.chunk_overlap,
        chunk_strategy=knowledge_base.chunk_strategy,
    )
    vectors = await asyncio.to_thread(embedding.embed_documents, _embedding_texts(source, drafts))
    chunks, vector_points = _chunk_rows_and_points(
        knowledge_base=knowledge_base,
        document_id=document_id,
        source=source,
        drafts=drafts,
        vectors=vectors,
    )

    # Qdrant is written first. If the following SQL commit fails, the consistency
    # checker sees orphan point ids and a repair task can rebuild safely.
    await qdrant.vector_store.upsert(knowledge_base.vector_collection_name, vector_points)
    new_point_ids = {point.id for point in vector_points}
    await qdrant.vector_store.delete_points(
        knowledge_base.vector_collection_name, old_point_ids - new_point_ids
    )

    if document is None:
        document = Document(
            id=document_id,
            knowledge_base_id=knowledge_base.id,
            source_type=source.source_type,
            status=DocumentStatus.PROCESSING,
            title=source.title,
            canonical_uri=source.canonical_uri,
        )
        session.add(document)
    else:
        if document.cleaned_content and document.content_hash != content_hash:
            session.add(
                DocumentRevision(
                    document_id=document.id,
                    version=document.version,
                    title=document.title,
                    content_hash=document.content_hash,
                    cleaned_content=document.cleaned_content,
                    extra_metadata=document.extra_metadata,
                )
            )
        document.version += 1
    document.status = DocumentStatus.PROCESSING
    document.source_type = source.source_type
    document.title = source.title
    document.file_name = source.file_name
    document.mime_type = source.mime_type
    document.source_uri = source.source_uri
    document.canonical_uri = source.canonical_uri
    document.language = source.language
    document.content_hash = content_hash
    document.raw_content = source.content
    document.cleaned_content = source.content
    document.fetched_at = datetime.now(UTC)
    document.extra_metadata = source.metadata
    document.enabled = True
    document.vector_sync_status = VectorSyncStatus.PENDING
    document.vector_sync_error = None
    evaluation_targets = await _detach_evaluation_chunk_targets(session, [document.id])
    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    session.add_all(chunks)
    await session.flush()
    _reattach_evaluation_chunk_targets(evaluation_targets, chunks)
    task.document_id = task.document_id or document.id
    document.status = DocumentStatus.READY
    document.vector_sync_status = VectorSyncStatus.SYNCED
    document.indexed_at = datetime.now(UTC)
    await session.commit()
    return document, len(drafts)


async def _load_task_context(
    database: Database, task_id: UUID
) -> tuple[AsyncSession, IngestionTask, KnowledgeBase]:
    session = database.session_factory()
    task = await session.get(IngestionTask, task_id)
    if task is None:
        await session.close()
        raise ValueError(f"ingestion task {task_id} does not exist")
    knowledge_base = await session.get(KnowledgeBase, task.knowledge_base_id)
    if knowledge_base is None:
        await session.close()
        raise ValueError(f"knowledge base {task.knowledge_base_id} does not exist")
    task.started_at = task.started_at or datetime.now(UTC)
    task.attempt_count += 1
    await session.commit()
    return session, task, knowledge_base


async def _record_failure(
    database: Database,
    task_id: UUID,
    exc: Exception,
    *,
    completed_items: int = 0,
) -> None:
    async with database.session_factory() as session:
        task = await session.get(IngestionTask, task_id)
        if task is None or task.status == IngestionTaskStatus.CANCELLED:
            return
        task.status = (
            IngestionTaskStatus.PARTIALLY_COMPLETED
            if completed_items
            else IngestionTaskStatus.FAILED
        )
        task.current_stage = "部分完成, 等待重试" if completed_items else "处理失败"
        task.error_code = type(exc).__name__
        task.error_message = str(exc)[:2000]
        task.finished_at = datetime.now(UTC)
        task.result = {**task.result, "completed_items": completed_items}
        await session.commit()


async def _adopt_or_validate_signature(
    session: AsyncSession, knowledge_base: KnowledgeBase, embedding: EmbeddingService
) -> None:
    if knowledge_base.embedding_signature == "0" * 64:
        knowledge_base.embedding_signature = embedding.signature
        await session.commit()
    elif knowledge_base.embedding_signature != embedding.signature:
        raise RuntimeError(
            "knowledge base vector-space signature does not match its stored model configuration; "
            "run a full reindex"
        )


async def run_web_ingestion(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    completed_documents = 0
    indexed_chunks = 0
    session: AsyncSession | None = None
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        embedding = embedding_for_knowledge_base(settings, knowledge_base)
        await _adopt_or_validate_signature(session, knowledge_base, embedding)
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.CRAWLING, progress=5, stage="抓取网页"
        )
        seed_url = str(task.payload["seed_url"])
        max_pages = int(task.payload.get("max_pages", settings.crawler_default_max_pages))
        crawler = WebCrawler(settings)
        pages = await crawler.crawl(seed_url, max_pages=max_pages)
        if not pages:
            raise RuntimeError("crawler did not return any indexable pages")
        await qdrant.vector_store.ensure_collection(
            knowledge_base.vector_collection_name, knowledge_base.embedding_dimension
        )
        stored_document_count = int(
            await session.scalar(
                select(func.count(Document.id)).where(
                    Document.knowledge_base_id == knowledge_base.id
                )
            )
            or 0
        )
        quota_skipped = 0

        for index, page in enumerate(pages):
            existing_id = await session.scalar(
                select(Document.id).where(
                    Document.knowledge_base_id == knowledge_base.id,
                    Document.canonical_uri == page.canonical_url,
                )
            )
            if (
                existing_id is None
                and stored_document_count >= settings.max_documents_per_knowledge_base
            ):
                quota_skipped += 1
                continue
            base = 15 + int((index / len(pages)) * 80)
            await _set_task_stage(
                session,
                task,
                status=IngestionTaskStatus.PARSING,
                progress=base,
                stage=f"解析 {index + 1}/{len(pages)}: {page.title[:36]}",
            )
            await _set_task_stage(
                session,
                task,
                status=IngestionTaskStatus.CHUNKING,
                progress=min(base + 2, 94),
                stage=f"切片 {index + 1}/{len(pages)}",
            )
            await _set_task_stage(
                session,
                task,
                status=IngestionTaskStatus.EMBEDDING,
                progress=min(base + 4, 96),
                stage=f"向量化 {index + 1}/{len(pages)}: {page.title[:36]}",
            )
            _, chunk_count = await _index_source(
                session=session,
                task=task,
                knowledge_base=knowledge_base,
                source=_source_from_page(page),
                embedding=embedding,
                qdrant=qdrant,
            )
            await _set_task_stage(
                session,
                task,
                status=IngestionTaskStatus.INDEXING,
                progress=min(base + 6, 98),
                stage=f"写入索引 {index + 1}/{len(pages)}",
            )
            completed_documents += int(chunk_count > 0)
            stored_document_count += int(existing_id is None and chunk_count > 0)
            indexed_chunks += chunk_count

        partial = bool(crawler.report.errors or quota_skipped)
        task.status = (
            IngestionTaskStatus.PARTIALLY_COMPLETED if partial else IngestionTaskStatus.COMPLETED
        )
        task.progress = 100
        task.current_stage = "入库完成, 部分页面跳过" if partial else "入库完成"
        task.finished_at = datetime.now(UTC)
        task.error_code = None
        task.error_message = None
        task.result = {
            "documents": completed_documents,
            "chunks": indexed_chunks,
            "discovered_pages": len(pages),
            "quota_skipped": quota_skipped,
            "crawl_report": {
                "visited_urls": crawler.report.visited_urls,
                "indexed_pages": crawler.report.indexed_pages,
                "skipped_by_robots": crawler.report.skipped_by_robots,
                "errors": list(crawler.report.errors),
            },
        }
        await session.commit()
        return {
            "status": "partially_completed" if partial else "completed",
            "documents": completed_documents,
            "chunks": indexed_chunks,
        }
    except TaskCancelled:
        return {"status": "cancelled", "documents": completed_documents, "chunks": indexed_chunks}
    except Exception as exc:
        await _record_failure(database, task_id, exc, completed_items=completed_documents)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def run_file_ingestion(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    session: AsyncSession | None = None
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        embedding = embedding_for_knowledge_base(settings, knowledge_base)
        await _adopt_or_validate_signature(session, knowledge_base, embedding)
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.PARSING, progress=10, stage="解析上传文件"
        )
        path = Path(str(task.payload["stored_path"]))
        source = await asyncio.to_thread(
            parse_uploaded_document,
            path,
            file_name=str(task.payload["file_name"]),
            mime_type=str(task.payload.get("mime_type") or "application/octet-stream"),
            canonical_uri=str(task.payload["canonical_uri"]),
        )
        await qdrant.vector_store.ensure_collection(
            knowledge_base.vector_collection_name, knowledge_base.embedding_dimension
        )
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.CHUNKING, progress=30, stage="切分文本"
        )
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.EMBEDDING, progress=50, stage="生成向量"
        )
        document, chunk_count = await _index_source(
            session=session,
            task=task,
            knowledge_base=knowledge_base,
            source=source,
            embedding=embedding,
            qdrant=qdrant,
        )
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.INDEXING, progress=90, stage="写入 Qdrant"
        )
        task.status = IngestionTaskStatus.COMPLETED
        task.progress = 100
        task.current_stage = "文件入库完成"
        task.finished_at = datetime.now(UTC)
        task.result = {"document_id": str(document.id), "chunks": chunk_count}
        await session.commit()
        try:
            remove_uploaded_file(settings.upload_dir, path)
        except OSError:
            logger.warning(
                "completed_upload_cleanup_failed",
                extra={"task_id": str(task.id), "stored_path": str(path)},
                exc_info=True,
            )
        return {"status": "completed", "documents": 1, "chunks": chunk_count}
    except TaskCancelled:
        return {"status": "cancelled", "documents": 0, "chunks": 0}
    except Exception as exc:
        await _record_failure(database, task_id, exc)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def run_document_reindex(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    session: AsyncSession | None = None
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        document_id = UUID(str(task.payload["document_id"]))
        document = await session.get(Document, document_id)
        if document is None or document.knowledge_base_id != knowledge_base.id:
            raise ValueError("document does not exist in this knowledge base")
        if not document.cleaned_content:
            raise ValueError("document has no cleaned content to reindex")
        embedding = embedding_for_knowledge_base(settings, knowledge_base)
        await _adopt_or_validate_signature(session, knowledge_base, embedding)
        await qdrant.vector_store.ensure_collection(
            knowledge_base.vector_collection_name, knowledge_base.embedding_dimension
        )
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.CHUNKING, progress=20, stage="重新切片"
        )
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.EMBEDDING, progress=45, stage="重新生成向量"
        )
        source = SourceDocument(
            title=document.title,
            content=document.cleaned_content,
            source_type=document.source_type,
            source_uri=document.source_uri,
            canonical_uri=document.canonical_uri or f"document://{document.id}",
            language=document.language,
            file_name=document.file_name,
            mime_type=document.mime_type,
            metadata=document.extra_metadata,
        )
        _, chunk_count = await _index_source(
            session=session,
            task=task,
            knowledge_base=knowledge_base,
            source=source,
            embedding=embedding,
            qdrant=qdrant,
            force=True,
        )
        task.status = IngestionTaskStatus.COMPLETED
        task.progress = 100
        task.current_stage = "文档重建完成"
        task.finished_at = datetime.now(UTC)
        task.result = {"document_id": str(document.id), "chunks": chunk_count}
        await session.commit()
        return {"status": "completed", "documents": 1, "chunks": chunk_count}
    except TaskCancelled:
        return {"status": "cancelled", "documents": 0, "chunks": 0}
    except Exception as exc:
        await _record_failure(database, task_id, exc)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def run_knowledge_base_reindex(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    session: AsyncSession | None = None
    new_collection: str | None = None
    switched = False
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        config = task.payload.get("configuration", {})
        model_name = str(config.get("embedding_model") or knowledge_base.embedding_model)
        revision = str(config.get("embedding_revision") or knowledge_base.embedding_revision)
        dimension = int(config.get("embedding_dimension") or knowledge_base.embedding_dimension)
        query_prefix = str(
            config.get("embedding_query_prefix")
            if config.get("embedding_query_prefix") is not None
            else knowledge_base.embedding_query_prefix
        )
        passage_prefix = str(
            config.get("embedding_passage_prefix")
            if config.get("embedding_passage_prefix") is not None
            else knowledge_base.embedding_passage_prefix
        )
        chunk_size = int(config.get("chunk_size") or knowledge_base.chunk_size)
        chunk_overlap = int(
            config.get("chunk_overlap")
            if config.get("chunk_overlap") is not None
            else knowledge_base.chunk_overlap
        )
        chunk_strategy = str(config.get("chunk_strategy") or knowledge_base.chunk_strategy)
        if chunk_strategy not in {"character", "token"}:
            raise ValueError("chunk_strategy must be character or token")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        embedding = embedding_for_configuration(
            settings,
            model_name=model_name,
            revision=revision,
            dimension=dimension,
            query_prefix=query_prefix,
            passage_prefix=passage_prefix,
        )
        next_version = knowledge_base.index_version + 1
        new_collection = f"studyrag_{knowledge_base.id.hex}_v{next_version}_{task.id.hex[:8]}"
        await qdrant.vector_store.ensure_collection(new_collection, dimension)
        documents = list(
            await session.scalars(
                select(Document).where(
                    Document.knowledge_base_id == knowledge_base.id,
                    Document.cleaned_content.is_not(None),
                    Document.status != DocumentStatus.DELETING,
                )
            )
        )
        replacement_chunks: list[Chunk] = []
        total_chunks = 0
        old_signature = knowledge_base.embedding_signature
        for index, document in enumerate(documents):
            await _set_task_stage(
                session,
                task,
                status=IngestionTaskStatus.CHUNKING,
                progress=5 + int((index / max(1, len(documents))) * 85),
                stage=f"重建 {index + 1}/{len(documents)}: {document.title[:36]}",
            )
            content = document.cleaned_content or ""
            drafts = _split_document(
                content,
                embedding=embedding,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chunk_strategy=chunk_strategy,
            )
            source = SourceDocument(
                title=document.title,
                content=content,
                source_type=document.source_type,
                source_uri=document.source_uri,
                canonical_uri=document.canonical_uri or f"document://{document.id}",
                language=document.language,
                file_name=document.file_name,
                mime_type=document.mime_type,
                metadata=document.extra_metadata,
            )
            vectors = await asyncio.to_thread(
                embedding.embed_documents, _embedding_texts(source, drafts)
            )
            chunks, points = _chunk_rows_and_points(
                knowledge_base=knowledge_base,
                document_id=document.id,
                source=source,
                drafts=drafts,
                vectors=vectors,
                index_version=next_version,
                model_signature=embedding.signature,
            )
            replacement_chunks.extend(chunks)
            total_chunks += len(chunks)
            if document.enabled:
                await qdrant.vector_store.upsert(new_collection, points)

        await _set_task_stage(
            session,
            task,
            status=IngestionTaskStatus.INDEXING,
            progress=94,
            stage="原子切换索引版本",
        )
        document_ids = [document.id for document in documents]
        evaluation_targets = await _detach_evaluation_chunk_targets(session, document_ids)
        if document_ids:
            await session.execute(delete(Chunk).where(Chunk.document_id.in_(document_ids)))
        session.add_all(replacement_chunks)
        await session.flush()
        _reattach_evaluation_chunk_targets(evaluation_targets, replacement_chunks)
        now = datetime.now(UTC)
        for document in documents:
            document.status = DocumentStatus.READY
            document.vector_sync_status = VectorSyncStatus.SYNCED
            document.vector_sync_error = None
            document.indexed_at = now
        old_collection = knowledge_base.vector_collection_name
        knowledge_base.embedding_model = model_name
        knowledge_base.embedding_revision = revision
        knowledge_base.embedding_dimension = dimension
        knowledge_base.embedding_query_prefix = query_prefix
        knowledge_base.embedding_passage_prefix = passage_prefix
        knowledge_base.embedding_signature = embedding.signature
        knowledge_base.chunk_size = chunk_size
        knowledge_base.chunk_overlap = chunk_overlap
        knowledge_base.chunk_strategy = chunk_strategy
        knowledge_base.index_version = next_version
        knowledge_base.vector_collection_name = new_collection
        task.status = IngestionTaskStatus.COMPLETED
        task.progress = 100
        task.current_stage = "知识库重建完成"
        task.finished_at = now
        task.result = {
            "documents": len(documents),
            "chunks": total_chunks,
            "old_collection": old_collection,
            "new_collection": new_collection,
            "old_signature": old_signature,
            "new_signature": embedding.signature,
        }
        await session.commit()
        switched = True
        try:
            await qdrant.vector_store.delete_collection(old_collection)
        except Exception as cleanup_error:
            logger.warning(
                "old_vector_collection_cleanup_failed",
                extra={
                    "knowledge_base_id": str(knowledge_base.id),
                    "old_collection": old_collection,
                    "new_collection": new_collection,
                    "error": str(cleanup_error),
                },
                exc_info=True,
            )
            task.result = {
                **task.result,
                "cleanup_warning": f"old collection retained: {old_collection}",
            }
            await session.commit()
        return {"status": "completed", "documents": len(documents), "chunks": total_chunks}
    except TaskCancelled:
        if new_collection and not switched:
            await qdrant.vector_store.delete_collection(new_collection)
        return {"status": "cancelled", "documents": 0, "chunks": 0}
    except Exception as exc:
        if session is not None:
            await session.rollback()
        if new_collection and not switched:
            await qdrant.vector_store.delete_collection(new_collection)
        await _record_failure(database, task_id, exc)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def run_document_delete(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    session: AsyncSession | None = None
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        document_id = UUID(str(task.payload["document_id"]))
        document = await session.get(Document, document_id)
        if document is None:
            task.status = IngestionTaskStatus.COMPLETED
            task.progress = 100
            task.current_stage = "文档已不存在"
            task.finished_at = datetime.now(UTC)
            await session.commit()
            return {"status": "completed", "documents": 0, "chunks": 0}
        document.status = DocumentStatus.DELETING
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.INDEXING, progress=30, stage="删除向量"
        )
        await qdrant.vector_store.delete_document_points(
            knowledge_base.vector_collection_name, document_id
        )
        await session.delete(document)
        task.document_id = None
        task.status = IngestionTaskStatus.COMPLETED
        task.progress = 100
        task.current_stage = "文档已删除"
        task.finished_at = datetime.now(UTC)
        task.result = {"deleted_document_id": str(document_id)}
        await session.commit()
        return {"status": "completed", "documents": 1, "chunks": 0}
    except TaskCancelled:
        return {"status": "cancelled", "documents": 0, "chunks": 0}
    except Exception as exc:
        await _record_failure(database, task_id, exc)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def run_knowledge_base_delete(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    qdrant = QdrantManager(settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    session: AsyncSession | None = None
    try:
        session, task, knowledge_base = await _load_task_context(database, task_id)
        await _set_task_stage(
            session, task, status=IngestionTaskStatus.INDEXING, progress=30, stage="删除向量集合"
        )
        await qdrant.vector_store.delete_collection(knowledge_base.vector_collection_name)
        knowledge_base_id = knowledge_base.id
        await session.delete(knowledge_base)
        await session.commit()
        try:
            remove_knowledge_base_uploads(settings.upload_dir, knowledge_base_id)
        except OSError:
            logger.warning(
                "knowledge_base_upload_cleanup_failed",
                extra={"knowledge_base_id": str(knowledge_base_id)},
                exc_info=True,
            )
        return {"status": "completed", "documents": 0, "chunks": 0}
    except TaskCancelled:
        return {"status": "cancelled", "documents": 0, "chunks": 0}
    except Exception as exc:
        await _record_failure(database, task_id, exc)
        raise
    finally:
        if session is not None:
            await session.close()
        await qdrant.close()
        await database.close()


async def execute_ingestion_task(task_id: UUID, settings: Settings) -> dict[str, int | str]:
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        async with database.session_factory() as session:
            task = await session.get(IngestionTask, task_id)
            if task is None:
                raise ValueError(f"ingestion task {task_id} does not exist")
            task_type = task.task_type.value
            kind = str(task.payload.get("kind", "web"))
    finally:
        await database.close()

    if task_type == "ingest_document" and kind == "web":
        return await run_web_ingestion(task_id, settings)
    if task_type == "ingest_document" and kind == "file":
        return await run_file_ingestion(task_id, settings)
    if task_type == "reindex_document":
        return await run_document_reindex(task_id, settings)
    if task_type in {"reindex_knowledge_base", "consistency_repair"}:
        return await run_knowledge_base_reindex(task_id, settings)
    if task_type == "delete_document":
        return await run_document_delete(task_id, settings)
    if task_type == "delete_knowledge_base":
        return await run_knowledge_base_delete(task_id, settings)
    raise ValueError(f"unsupported ingestion task type: {task_type}/{kind}")
