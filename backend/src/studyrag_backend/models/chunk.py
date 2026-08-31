from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studyrag_backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from studyrag_backend.models.document import Document


class Chunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "sequence_index", name="uq_chunks_document_sequence"),
        CheckConstraint("sequence_index >= 0", name="sequence_index_nonnegative"),
        CheckConstraint("character_count >= 0", name="character_count_nonnegative"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="token_count_nonnegative"),
        CheckConstraint(
            "start_offset IS NULL OR end_offset IS NULL OR start_offset <= end_offset",
            name="offset_order",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    character_count: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int | None] = mapped_column(nullable=True)
    vector_point_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    start_offset: Mapped[int | None] = mapped_column(nullable=True)
    end_offset: Mapped[int | None] = mapped_column(nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
