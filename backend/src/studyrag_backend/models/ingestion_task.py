from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studyrag_backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from studyrag_backend.models.enums import IngestionTaskStatus, IngestionTaskType, enum_values

if TYPE_CHECKING:
    from studyrag_backend.models.document import Document
    from studyrag_backend.models.knowledge_base import KnowledgeBase


class IngestionTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_tasks"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_percentage"),
        CheckConstraint(
            "task_type IN ('ingest_document', 'reindex_document', 'export_knowledge_base', "
            "'reindex_knowledge_base', 'delete_document', 'delete_knowledge_base', "
            "'consistency_repair')",
            name="ingestion_task_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'crawling', 'parsing', 'chunking', 'embedding', "
            "'indexing', 'retrying', 'completed', 'failed', 'cancelled', "
            "'partially_completed', 'paused')",
            name="ingestion_task_status",
        ),
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    task_type: Mapped[IngestionTaskType] = mapped_column(
        Enum(
            IngestionTaskType,
            name="ingestion_task_type",
            length=40,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[IngestionTaskStatus] = mapped_column(
        Enum(
            IngestionTaskStatus,
            name="ingestion_task_status",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=IngestionTaskStatus.PENDING,
        server_default=IngestionTaskStatus.PENDING.value,
        index=True,
    )
    progress: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    current_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pause_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    retry_of_task_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="ingestion_tasks")
    document: Mapped[Document | None] = relationship(back_populates="ingestion_tasks")
