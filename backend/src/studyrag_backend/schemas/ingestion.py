from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from studyrag_backend.models.enums import (
    DocumentSourceType,
    DocumentStatus,
    IngestionTaskStatus,
    IngestionTaskType,
)


class WebImportCreate(BaseModel):
    seed_url: AnyHttpUrl
    max_pages: int = Field(default=40, ge=1, le=100)


class IngestionTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    document_id: UUID | None
    celery_task_id: str | None
    task_type: IngestionTaskType
    status: IngestionTaskStatus
    progress: int
    current_stage: str | None
    attempt_count: int
    cancel_requested: bool
    pause_requested: bool
    retry_of_task_id: UUID | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    payload: dict[str, object]
    result: dict[str, object]
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    source_type: DocumentSourceType
    status: DocumentStatus
    title: str
    file_name: str | None
    mime_type: str | None
    source_uri: str | None
    canonical_uri: str | None
    language: str | None
    content_hash: str | None
    fetched_at: datetime | None
    indexed_at: datetime | None
    version: int
    enabled: bool
    vector_sync_status: str
    vector_sync_error: str | None
    extra_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    language: str | None = Field(default=None, max_length=32)
    extra_metadata: dict[str, object] | None = None


class DocumentRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version: int
    title: str
    content_hash: str | None
    cleaned_content: str | None
    extra_metadata: dict[str, object]
    created_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    sequence_index: int
    content: str
    content_hash: str
    character_count: int
    token_count: int | None
    vector_point_id: UUID
    start_offset: int | None
    end_offset: int | None
    extra_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


class ChunkContextRead(BaseModel):
    chunk: ChunkRead
    previous_chunk: ChunkRead | None = None
    next_chunk: ChunkRead | None = None
    title: str
    source_uri: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str | None = Field(default=None, pattern="^(semantic|keyword|hybrid)$")
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    language: str | None = Field(default=None, max_length=32)
    source_type: DocumentSourceType | None = None
    use_reranker: bool = False
    expand_query: bool = True


class SearchHit(BaseModel):
    score: float
    semantic_score: float | None = None
    keyword_score: float | None = None
    reranker_score: float | None = None
    match_type: str
    chunk_id: UUID
    document_id: UUID
    sequence_index: int
    content: str
    title: str
    source_uri: str | None
    section_heading: str | None = None
    character_count: int


class ConsistencyReport(BaseModel):
    consistent: bool
    postgres_chunk_count: int
    qdrant_point_count: int
    missing_point_ids: list[UUID]
    orphan_point_ids: list[UUID]
    model_signature_matches: bool
    checked_at: datetime
