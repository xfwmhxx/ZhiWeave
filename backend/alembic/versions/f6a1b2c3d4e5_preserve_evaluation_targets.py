"""Preserve evaluation cases when chunks are replaced.

Revision ID: f6a1b2c3d4e5
Revises: d71a4c8f5b20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a1b2c3d4e5"
down_revision: str | None = "d71a4c8f5b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PINNED_E5_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
EVALUATION_CHUNK_FK = (
    "fk_retrieval_evaluation_cases_relevant_chunk_id_chunks"
)


def upgrade() -> None:
    op.drop_constraint(
        EVALUATION_CHUNK_FK,
        "retrieval_evaluation_cases",
        type_="foreignkey",
    )
    op.create_foreign_key(
        EVALUATION_CHUNK_FK,
        "retrieval_evaluation_cases",
        "chunks",
        ["relevant_chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "knowledge_bases",
        "embedding_revision",
        existing_type=sa.String(length=120),
        server_default=PINNED_E5_REVISION,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_bases",
        "embedding_revision",
        existing_type=sa.String(length=120),
        server_default="main",
        existing_nullable=False,
    )
    op.drop_constraint(
        EVALUATION_CHUNK_FK,
        "retrieval_evaluation_cases",
        type_="foreignkey",
    )
    op.create_foreign_key(
        EVALUATION_CHUNK_FK,
        "retrieval_evaluation_cases",
        "chunks",
        ["relevant_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
