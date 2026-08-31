from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from studyrag_backend.api.dependencies import DatabaseSession, get_knowledge_base, request_settings
from studyrag_backend.infrastructure.embedding import EmbeddingRegistry
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.evaluation_case import RetrievalEvaluationCase
from studyrag_backend.schemas.ingestion import SearchHit, SearchRequest
from studyrag_backend.schemas.retrieval import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationCaseResult,
    EvaluationReport,
    EvaluationRunRequest,
)
from studyrag_backend.services.retrieval import search

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}", tags=["retrieval"])


async def _search(
    knowledge_base_id: UUID,
    payload: SearchRequest,
    request: Request,
    session: DatabaseSession,
) -> list[SearchHit]:
    knowledge_base = await get_knowledge_base(session, knowledge_base_id)
    try:
        return await search(
            session=session,
            knowledge_base=knowledge_base,
            payload=payload,
            registry=cast(EmbeddingRegistry, request.app.state.embedding_registry),
            qdrant=cast(QdrantManager, request.app.state.qdrant),
            settings=request_settings(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/search", response_model=list[SearchHit])
async def search_knowledge_base(
    knowledge_base_id: UUID,
    payload: SearchRequest,
    request: Request,
    session: DatabaseSession,
) -> list[SearchHit]:
    return await _search(knowledge_base_id, payload, request, session)


@router.post(
    "/evaluation-cases",
    response_model=EvaluationCaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation_case(
    knowledge_base_id: UUID,
    payload: EvaluationCaseCreate,
    session: DatabaseSession,
) -> RetrievalEvaluationCase:
    await get_knowledge_base(session, knowledge_base_id)
    if payload.relevant_document_id:
        document = await session.get(Document, payload.relevant_document_id)
        if document is None or document.knowledge_base_id != knowledge_base_id:
            raise HTTPException(
                status_code=422, detail="relevant document is outside this knowledge base"
            )
    if payload.relevant_chunk_id:
        row = await session.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id == payload.relevant_chunk_id)
        )
        match = row.first()
        if match is None or match[1].knowledge_base_id != knowledge_base_id:
            raise HTTPException(
                status_code=422, detail="relevant chunk is outside this knowledge base"
            )
    case = RetrievalEvaluationCase(knowledge_base_id=knowledge_base_id, **payload.model_dump())
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


@router.get("/evaluation-cases", response_model=list[EvaluationCaseRead])
async def list_evaluation_cases(
    knowledge_base_id: UUID, session: DatabaseSession
) -> list[RetrievalEvaluationCase]:
    await get_knowledge_base(session, knowledge_base_id)
    result = await session.scalars(
        select(RetrievalEvaluationCase)
        .where(RetrievalEvaluationCase.knowledge_base_id == knowledge_base_id)
        .order_by(RetrievalEvaluationCase.created_at)
    )
    return list(result)


@router.delete("/evaluation-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_case(
    knowledge_base_id: UUID, case_id: UUID, session: DatabaseSession
) -> None:
    await get_knowledge_base(session, knowledge_base_id)
    case = await session.get(RetrievalEvaluationCase, case_id)
    if case is None or case.knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=404, detail="Evaluation case not found")
    await session.delete(case)
    await session.commit()


@router.post("/evaluation-runs", response_model=EvaluationReport)
async def run_evaluation(
    knowledge_base_id: UUID,
    payload: EvaluationRunRequest,
    request: Request,
    session: DatabaseSession,
) -> EvaluationReport:
    cases = list(
        await session.scalars(
            select(RetrievalEvaluationCase)
            .where(RetrievalEvaluationCase.knowledge_base_id == knowledge_base_id)
            .order_by(RetrievalEvaluationCase.created_at)
        )
    )
    if not cases:
        raise HTTPException(status_code=422, detail="add at least one evaluation case first")
    results: list[EvaluationCaseResult] = []
    reciprocal_rank_sum = 0.0
    hit_count = 0
    for case in cases:
        hits = await _search(
            knowledge_base_id,
            SearchRequest(query=case.query, top_k=payload.top_k, mode=payload.mode.value),
            request,
            session,
        )
        rank = next(
            (
                index
                for index, hit in enumerate(hits, start=1)
                if (case.relevant_chunk_id and hit.chunk_id == case.relevant_chunk_id)
                or (
                    case.relevant_chunk_id is None
                    and case.relevant_document_id
                    and hit.document_id == case.relevant_document_id
                )
            ),
            None,
        )
        if rank is not None:
            hit_count += 1
            reciprocal_rank_sum += 1 / rank
        results.append(
            EvaluationCaseResult(case_id=case.id, query=case.query, hit=rank is not None, rank=rank)
        )
    case_count = len(cases)
    return EvaluationReport(
        mode=payload.mode,
        top_k=payload.top_k,
        case_count=case_count,
        hit_rate=hit_count / case_count,
        recall_at_k=hit_count / case_count,
        mean_reciprocal_rank=reciprocal_rank_sum / case_count,
        results=results,
    )
