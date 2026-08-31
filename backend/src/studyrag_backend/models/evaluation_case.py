from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studyrag_backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from studyrag_backend.models.knowledge_base import KnowledgeBase


class RetrievalEvaluationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_evaluation_cases"

    knowledge_base_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    relevant_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    relevant_chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    knowledge_base: Mapped[KnowledgeBase] = relationship()
