from uuid import uuid4

from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.evaluation_case import RetrievalEvaluationCase
from studyrag_backend.services.ingestion import (
    _EvaluationChunkTarget,
    _reattach_evaluation_chunk_targets,
)


def _chunk(document_id, *, sequence: int, content_hash: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=document_id,
        sequence_index=sequence,
        content="content",
        content_hash=content_hash,
        character_count=7,
        token_count=1,
        vector_point_id=uuid4(),
        start_offset=0,
        end_offset=7,
        extra_metadata={},
    )


def test_evaluation_target_rebinds_to_logically_identical_chunk() -> None:
    document_id = uuid4()
    case = RetrievalEvaluationCase(
        knowledge_base_id=uuid4(), query="question", relevant_document_id=document_id
    )
    replacement = _chunk(document_id, sequence=3, content_hash="stable-hash")
    target = _EvaluationChunkTarget(case, document_id, 3, "stable-hash")

    _reattach_evaluation_chunk_targets([target], [replacement])

    assert case.relevant_chunk_id == replacement.id


def test_evaluation_target_falls_back_to_document_when_chunk_boundaries_change() -> None:
    document_id = uuid4()
    case = RetrievalEvaluationCase(
        knowledge_base_id=uuid4(), query="question", relevant_document_id=document_id
    )
    target = _EvaluationChunkTarget(case, document_id, 3, "old-hash")

    _reattach_evaluation_chunk_targets(
        [target], [_chunk(document_id, sequence=3, content_hash="new-hash")]
    )

    assert case.relevant_chunk_id is None
    assert case.relevant_document_id == document_id
