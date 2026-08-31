from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from studyrag_backend.models.enums import KnowledgeBaseStatus, RetrievalMode


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)
    chunk_strategy: str | None = Field(default=None, pattern="^(character|token)$")


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: KnowledgeBaseStatus | None = None
    retrieval_mode: RetrievalMode | None = None
    semantic_weight: float | None = Field(default=None, ge=0, le=1)
    keyword_weight: float | None = Field(default=None, ge=0, le=1)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    reranker_model: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_weights(self) -> "KnowledgeBaseUpdate":
        if (
            self.semantic_weight is not None
            and self.keyword_weight is not None
            and self.semantic_weight + self.keyword_weight <= 0
        ):
            raise ValueError("semantic_weight + keyword_weight must be greater than zero")
        return self


class KnowledgeBaseReindex(BaseModel):
    embedding_model: str | None = Field(default=None, min_length=1, max_length=255)
    embedding_revision: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_dimension: int | None = Field(default=None, ge=1, le=8192)
    embedding_query_prefix: str | None = Field(default=None, max_length=80)
    embedding_passage_prefix: str | None = Field(default=None, max_length=80)
    chunk_size: int | None = Field(default=None, ge=100, le=2000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)
    chunk_strategy: str | None = Field(default=None, pattern="^(character|token)$")


class KnowledgeBaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: str
    name: str
    description: str | None
    status: KnowledgeBaseStatus
    embedding_model: str
    embedding_revision: str
    embedding_dimension: int
    embedding_query_prefix: str
    embedding_passage_prefix: str
    embedding_signature: str
    chunk_size: int
    chunk_overlap: int
    chunk_strategy: str
    vector_collection_name: str
    index_version: int
    retrieval_mode: RetrievalMode
    semantic_weight: float
    keyword_weight: float
    score_threshold: float | None
    reranker_model: str | None
    last_consistency_check_at: datetime | None
    last_consistency_report: dict[str, object]
    document_count: int = 0
    chunk_count: int = 0
    active_task_count: int = 0
    created_at: datetime
    updated_at: datetime
