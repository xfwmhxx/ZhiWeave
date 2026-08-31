import asyncio
import math
import re
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studyrag_backend.core.config import Settings
from studyrag_backend.infrastructure.embedding import EmbeddingRegistry
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.enums import DocumentStatus, RetrievalMode
from studyrag_backend.models.knowledge_base import KnowledgeBase
from studyrag_backend.schemas.ingestion import SearchHit, SearchRequest

_LATIN_WORD = re.compile(r"[a-z0-9_+#.-]+", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_QUERY_ALIASES = {
    "数据库": "database db",
    "向量": "vector embedding",
    "嵌入": "embedding vector",
    "检索": "retrieval search",
    "切片": "chunk split",
    "知识库": "knowledge base rag",
    "筛选": "filter where",
}


@dataclass(frozen=True, slots=True)
class _Candidate:
    chunk_id: UUID
    document_id: UUID
    sequence_index: int
    content: str
    title: str
    source_uri: str | None


def tokenize_mixed_text(value: str) -> list[str]:
    lowered = value.lower()
    tokens = _LATIN_WORD.findall(lowered)
    for run in _CJK_RUN.findall(lowered):
        tokens.extend(run)
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def expand_query_without_llm(query: str) -> str:
    expansions = [alias for term, alias in _QUERY_ALIASES.items() if term in query]
    camel_words = re.sub(r"([a-z])([A-Z])", r"\1 \2", query)
    return " ".join([query, camel_words, *expansions]).strip()


def _bm25_scores(query: str, candidates: list[_Candidate]) -> dict[UUID, float]:
    query_tokens = tokenize_mixed_text(query)
    if not query_tokens or not candidates:
        return {}
    documents = [
        tokenize_mixed_text(f"{candidate.title} {candidate.title} {candidate.content}")
        for candidate in candidates
    ]
    average_length = sum(map(len, documents)) / max(1, len(documents))
    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))
    raw_scores: dict[UUID, float] = {}
    total = len(documents)
    k1, b = 1.5, 0.75
    for candidate, tokens in zip(candidates, documents, strict=True):
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_tokens:
            frequency = frequencies[term]
            if not frequency:
                continue
            document_count = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (total - document_count + 0.5) / (document_count + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(tokens) / max(1.0, average_length))
            score += inverse_document_frequency * (frequency * (k1 + 1)) / denominator
        if score > 0:
            raw_scores[candidate.chunk_id] = score
    maximum = max(raw_scores.values(), default=1.0)
    return {chunk_id: score / maximum for chunk_id, score in raw_scores.items()}


async def _load_candidates(
    session: AsyncSession,
    knowledge_base_id: UUID,
    payload: SearchRequest,
) -> list[_Candidate]:
    statement = (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Document.knowledge_base_id == knowledge_base_id,
            Document.status == DocumentStatus.READY,
            Document.enabled.is_(True),
        )
    )
    if payload.language:
        statement = statement.where(Document.language == payload.language)
    if payload.source_type:
        statement = statement.where(Document.source_type == payload.source_type)
    rows = (await session.execute(statement)).all()
    return [
        _Candidate(
            chunk_id=chunk.id,
            document_id=document.id,
            sequence_index=chunk.sequence_index,
            content=chunk.content,
            title=document.title,
            source_uri=document.source_uri,
        )
        for chunk, document in rows
    ]


async def search(
    *,
    session: AsyncSession,
    knowledge_base: KnowledgeBase,
    payload: SearchRequest,
    registry: EmbeddingRegistry,
    qdrant: QdrantManager,
    settings: Settings,
) -> list[SearchHit]:
    mode = RetrievalMode(payload.mode or knowledge_base.retrieval_mode.value)
    candidates = await _load_candidates(session, knowledge_base.id, payload)
    candidate_by_id = {candidate.chunk_id: candidate for candidate in candidates}
    semantic_scores: dict[UUID, float] = {}
    semantic_ranks: dict[UUID, int] = {}
    keyword_scores: dict[UUID, float] = {}
    keyword_ranks: dict[UUID, int] = {}
    candidate_limit = max(payload.top_k * 5, settings.retrieval_candidate_limit)

    if mode in {RetrievalMode.SEMANTIC, RetrievalMode.HYBRID}:
        embedding = registry.get(
            model_name=knowledge_base.embedding_model,
            revision=knowledge_base.embedding_revision,
            dimension=knowledge_base.embedding_dimension,
            query_prefix=knowledge_base.embedding_query_prefix,
            passage_prefix=knowledge_base.embedding_passage_prefix,
        )
        if knowledge_base.embedding_signature == "0" * 64:
            knowledge_base.embedding_signature = embedding.signature
            await session.commit()
        elif knowledge_base.embedding_signature != embedding.signature:
            raise RuntimeError(
                "stored embedding configuration does not match the indexed vector space; "
                "run a knowledge-base reindex"
            )
        query_vector = await asyncio.to_thread(embedding.embed_query, payload.query.strip())
        semantic_hits = await qdrant.vector_store.search(
            collection=knowledge_base.vector_collection_name,
            knowledge_base_id=knowledge_base.id,
            vector=query_vector,
            limit=candidate_limit,
            score_threshold=(
                payload.score_threshold
                if payload.score_threshold is not None
                else knowledge_base.score_threshold
            ),
            language=payload.language,
            source_type=payload.source_type.value if payload.source_type else None,
        )
        for rank, hit in enumerate(semantic_hits, start=1):
            chunk_id = UUID(str(hit.payload["chunk_id"]))
            semantic_scores[chunk_id] = hit.score
            semantic_ranks[chunk_id] = rank
            if chunk_id not in candidate_by_id:
                candidate_by_id[chunk_id] = _Candidate(
                    chunk_id=chunk_id,
                    document_id=UUID(str(hit.payload["document_id"])),
                    sequence_index=int(hit.payload["sequence_index"]),
                    content=str(hit.payload["content"]),
                    title=str(hit.payload["title"]),
                    source_uri=(
                        str(hit.payload["source_uri"]) if hit.payload.get("source_uri") else None
                    ),
                )

    if mode in {RetrievalMode.KEYWORD, RetrievalMode.HYBRID}:
        lexical_query = (
            expand_query_without_llm(payload.query) if payload.expand_query else payload.query
        )
        keyword_scores = _bm25_scores(lexical_query, candidates)
        keyword_ranks = {
            chunk_id: rank
            for rank, (chunk_id, _) in enumerate(
                sorted(keyword_scores.items(), key=lambda item: item[1], reverse=True), start=1
            )
        }

    ids = set(semantic_ranks) | set(keyword_ranks)
    semantic_weight = knowledge_base.semantic_weight if mode != RetrievalMode.KEYWORD else 0.0
    keyword_weight = knowledge_base.keyword_weight if mode != RetrievalMode.SEMANTIC else 0.0
    weight_total = semantic_weight + keyword_weight
    rrf_denominator = weight_total / 61 if weight_total else 1.0
    combined: list[tuple[UUID, float]] = []
    for chunk_id in ids:
        rrf = 0.0
        if chunk_id in semantic_ranks:
            rrf += semantic_weight / (60 + semantic_ranks[chunk_id])
        if chunk_id in keyword_ranks:
            rrf += keyword_weight / (60 + keyword_ranks[chunk_id])
        if mode == RetrievalMode.SEMANTIC:
            final_score = semantic_scores[chunk_id]
        elif mode == RetrievalMode.KEYWORD:
            final_score = keyword_scores[chunk_id]
        else:
            final_score = min(1.0, rrf / rrf_denominator)
        combined.append((chunk_id, final_score))
    combined.sort(key=lambda item: item[1], reverse=True)
    combined = combined[:candidate_limit]

    reranker_scores: dict[UUID, float] = {}
    reranker_model = knowledge_base.reranker_model or settings.reranker_model_name
    if payload.use_reranker:
        if not reranker_model:
            raise ValueError("reranker is not configured for this knowledge base")
        texts = [candidate_by_id[chunk_id].content for chunk_id, _ in combined]
        scores = await asyncio.to_thread(registry.rerank, reranker_model, payload.query, texts)
        reranker_scores = {
            chunk_id: score for (chunk_id, _), score in zip(combined, scores, strict=True)
        }
        combined.sort(key=lambda item: reranker_scores[item[0]], reverse=True)

    results: list[SearchHit] = []
    for chunk_id, score in combined[: payload.top_k]:
        candidate = candidate_by_id[chunk_id]
        results.append(
            SearchHit(
                score=reranker_scores.get(chunk_id, score),
                semantic_score=semantic_scores.get(chunk_id),
                keyword_score=keyword_scores.get(chunk_id),
                reranker_score=reranker_scores.get(chunk_id),
                match_type=mode.value,
                chunk_id=chunk_id,
                document_id=candidate.document_id,
                sequence_index=candidate.sequence_index,
                content=candidate.content,
                title=candidate.title,
                source_uri=candidate.source_uri,
            )
        )
    return results
