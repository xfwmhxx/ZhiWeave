from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studyrag_backend.infrastructure.embedding import EmbeddingService
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.knowledge_base import KnowledgeBase
from studyrag_backend.schemas.ingestion import ConsistencyReport


async def inspect_consistency(
    session: AsyncSession,
    knowledge_base: KnowledgeBase,
    qdrant: QdrantManager,
    embedding: EmbeddingService,
) -> ConsistencyReport:
    postgres_ids = set(
        await session.scalars(
            select(Chunk.vector_point_id)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Document.knowledge_base_id == knowledge_base.id,
                Document.enabled.is_(True),
            )
        )
    )
    qdrant_ids = await qdrant.vector_store.collection_point_ids(
        knowledge_base.vector_collection_name
    )
    missing = sorted(postgres_ids - qdrant_ids, key=str)
    orphan = sorted(qdrant_ids - postgres_ids, key=str)
    signature_matches = knowledge_base.embedding_signature in {
        embedding.signature,
        "0" * 64,
    }
    checked_at = datetime.now(UTC)
    report = ConsistencyReport(
        consistent=not missing and not orphan and signature_matches,
        postgres_chunk_count=len(postgres_ids),
        qdrant_point_count=len(qdrant_ids),
        missing_point_ids=missing[:200],
        orphan_point_ids=orphan[:200],
        model_signature_matches=signature_matches,
        checked_at=checked_at,
    )
    knowledge_base.last_consistency_check_at = checked_at
    knowledge_base.last_consistency_report = report.model_dump(mode="json")
    await session.commit()
    return report
