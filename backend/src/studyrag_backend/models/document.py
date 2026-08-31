from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studyrag_backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from studyrag_backend.models.enums import (
    DocumentSourceType,
    DocumentStatus,
    VectorSyncStatus,
    enum_values,
)

if TYPE_CHECKING:
    from studyrag_backend.models.chunk import Chunk
    from studyrag_backend.models.ingestion_task import IngestionTask
    from studyrag_backend.models.knowledge_base import KnowledgeBase


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "canonical_uri",
            name="uq_documents_knowledge_base_canonical_uri",
        ),
        CheckConstraint(
            "source_type IN ('markdown', 'web_page', 'pdf', 'plain_text')",
            name="document_source_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed', 'deleting')",
            name="document_status",
        ),
        CheckConstraint("version > 0", name="document_version_positive"),
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(
            DocumentSourceType,
            name="document_source_type",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    vector_sync_status: Mapped[VectorSyncStatus] = mapped_column(
        Enum(
            VectorSyncStatus,
            name="vector_sync_status",
            length=20,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=VectorSyncStatus.PENDING,
        server_default=VectorSyncStatus.PENDING.value,
        index=True,
    )
    vector_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.sequence_index",
    )
    ingestion_tasks: Mapped[list[IngestionTask]] = relationship(
        back_populates="document",
        passive_deletes=True,
    )
