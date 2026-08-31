"""expand ingestion task type width

Revision ID: d71a4c8f5b20
Revises: c42e8f219a7c
Create Date: 2026-08-31 12:18:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d71a4c8f5b20"
down_revision: str | None = "c42e8f219a7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The original non-native SQLAlchemy Enum selected VARCHAR(21) from the old
    # longest value. New lifecycle operations such as `reindex_knowledge_base`
    # require additional room even though the check constraint already allows them.
    op.alter_column(
        "ingestion_tasks",
        "task_type",
        existing_type=sa.String(length=21),
        type_=sa.String(length=40),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "ingestion_tasks",
        "task_type",
        existing_type=sa.String(length=40),
        type_=sa.String(length=21),
        existing_nullable=False,
    )
