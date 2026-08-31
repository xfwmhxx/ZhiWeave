from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studyrag_backend.core.config import DEFAULT_EMBEDDING_MODEL_REVISION
from studyrag_backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from studyrag_backend.models.enums import KnowledgeBaseStatus, RetrievalMode, enum_values

if TYPE_CHECKING:
    from studyrag_backend.models.document import Document
    from studyrag_backend.models.ingestion_task import IngestionTask


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint("embedding_dimension > 0", name="embedding_dimension_positive"),
        CheckConstraint("chunk_size > 0", name="chunk_size_positive"),
        CheckConstraint("chunk_strategy IN ('character', 'token')", name="chunk_strategy_valid"),
        CheckConstraint(
            "chunk_overlap >= 0 AND chunk_overlap < chunk_size",
            name="chunk_overlap_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'deleting', 'failed')",
            name="knowledge_base_status",
        ),
        CheckConstraint("index_version > 0", name="index_version_positive"),
        CheckConstraint(
            "semantic_weight >= 0 AND keyword_weight >= 0 AND semantic_weight + keyword_weight > 0",
            name="retrieval_weights_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    workspace_id: Mapped[str] = mapped_column(
        String(120), nullable=False, default="local", server_default="local", index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(
            KnowledgeBaseStatus,
            name="knowledge_base_status",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=KnowledgeBaseStatus.ACTIVE,
        server_default=KnowledgeBaseStatus.ACTIVE.value,
    )
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_revision: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=DEFAULT_EMBEDDING_MODEL_REVISION,
        server_default=DEFAULT_EMBEDDING_MODEL_REVISION,
    )
    embedding_dimension: Mapped[int] = mapped_column(nullable=False)
    embedding_query_prefix: Mapped[str] = mapped_column(
        String(80), nullable=False, default="query: ", server_default="query: "
    )
    embedding_passage_prefix: Mapped[str] = mapped_column(
        String(80), nullable=False, default="passage: ", server_default="passage: "
    )
    embedding_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_size: Mapped[int] = mapped_column(nullable=False, default=480, server_default="480")
    chunk_overlap: Mapped[int] = mapped_column(nullable=False, default=80, server_default="80")
    chunk_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="character", server_default="character"
    )
    vector_collection_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    index_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    retrieval_mode: Mapped[RetrievalMode] = mapped_column(
        Enum(
            RetrievalMode,
            name="retrieval_mode",
            length=20,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=RetrievalMode.HYBRID,
        server_default=RetrievalMode.HYBRID.value,
    )
    semantic_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, server_default="0.7"
    )
    keyword_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.3, server_default="0.3"
    )
    score_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    reranker_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_consistency_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_consistency_report: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ingestion_tasks: Mapped[list[IngestionTask]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
