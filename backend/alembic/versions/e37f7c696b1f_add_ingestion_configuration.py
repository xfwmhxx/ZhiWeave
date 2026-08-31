"""add_ingestion_configuration

Revision ID: e37f7c696b1f
Revises: 9e27c568112e
Create Date: 2026-08-30 20:22:44.760429
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e37f7c696b1f"
down_revision: str | None = "9e27c568112e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_documents_knowledge_base_canonical_uri",
        "documents",
        ["knowledge_base_id", "canonical_uri"],
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("chunk_size", sa.Integer(), server_default="480", nullable=False),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("chunk_overlap", sa.Integer(), server_default="80", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_chunk_overlap_valid"),
        "knowledge_bases",
        "chunk_overlap >= 0 AND chunk_overlap < chunk_size",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_chunk_size_positive"),
        "knowledge_bases",
        "chunk_size > 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_knowledge_bases_chunk_size_positive"),
        "knowledge_bases",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_knowledge_bases_chunk_overlap_valid"),
        "knowledge_bases",
        type_="check",
    )
    op.drop_column("knowledge_bases", "chunk_overlap")
    op.drop_column("knowledge_bases", "chunk_size")
    op.drop_constraint("uq_documents_knowledge_base_canonical_uri", "documents", type_="unique")
    op.drop_column("documents", "fetched_at")
