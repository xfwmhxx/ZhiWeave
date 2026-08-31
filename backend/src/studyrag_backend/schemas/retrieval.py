from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from studyrag_backend.models.enums import RetrievalMode


class EvaluationCaseCreate(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    relevant_document_id: UUID | None = None
    relevant_chunk_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_relevance_target(self) -> "EvaluationCaseCreate":
        if self.relevant_document_id is None and self.relevant_chunk_id is None:
            raise ValueError("a relevant document or chunk is required")
        return self


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    query: str
    relevant_document_id: UUID | None
    relevant_chunk_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class EvaluationRunRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    mode: RetrievalMode = RetrievalMode.HYBRID


class EvaluationCaseResult(BaseModel):
    case_id: UUID
    query: str
    hit: bool
    rank: int | None


class EvaluationReport(BaseModel):
    mode: RetrievalMode
    top_k: int
    case_count: int
    hit_rate: float
    recall_at_k: float
    mean_reciprocal_rank: float
    results: list[EvaluationCaseResult]
