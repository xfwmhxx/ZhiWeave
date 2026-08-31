"""complete knowledge platform foundations

Revision ID: c42e8f219a7c
Revises: e37f7c696b1f
Create Date: 2026-08-31 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c42e8f219a7c"
down_revision: str | None = "e37f7c696b1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_knowledge_bases_knowledge_base_status"),
        "knowledge_bases",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_knowledge_base_status"),
        "knowledge_bases",
        "status IN ('active', 'archived', 'deleting', 'failed')",
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("embedding_revision", sa.String(120), server_default="main", nullable=False),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("workspace_id", sa.String(120), server_default="local", nullable=False),
    )
    op.create_index(op.f("ix_knowledge_bases_workspace_id"), "knowledge_bases", ["workspace_id"])
    op.add_column(
        "knowledge_bases",
        sa.Column("chunk_strategy", sa.String(20), server_default="character", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_chunk_strategy_valid"),
        "knowledge_bases",
        "chunk_strategy IN ('character', 'token')",
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "embedding_query_prefix", sa.String(80), server_default="query: ", nullable=False
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "embedding_passage_prefix", sa.String(80), server_default="passage: ", nullable=False
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("embedding_signature", sa.String(64), nullable=True),
    )
    # Existing vectors were produced by the then-global settings. A zero signature is a
    # deliberate legacy marker; the first read verifies the stored config and adopts the
    # deterministic signature without forcing a destructive rebuild.
    op.execute("UPDATE knowledge_bases SET embedding_signature = repeat('0', 64)")
    op.alter_column("knowledge_bases", "embedding_signature", nullable=False)
    op.add_column(
        "knowledge_bases",
        sa.Column("index_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("retrieval_mode", sa.String(20), server_default="hybrid", nullable=False),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("semantic_weight", sa.Float(), server_default="0.7", nullable=False),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("keyword_weight", sa.Float(), server_default="0.3", nullable=False),
    )
    op.add_column("knowledge_bases", sa.Column("score_threshold", sa.Float(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("reranker_model", sa.String(255), nullable=True))
    op.add_column(
        "knowledge_bases", sa.Column("last_consistency_check_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("last_consistency_report", sa.JSON(), server_default="{}", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_index_version_positive"),
        "knowledge_bases",
        "index_version > 0",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_retrieval_weights_valid"),
        "knowledge_bases",
        "semantic_weight >= 0 AND keyword_weight >= 0 AND semantic_weight + keyword_weight > 0",
    )

    op.drop_constraint(op.f("ck_documents_document_status"), "documents", type_="check")
    op.create_check_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        "status IN ('pending', 'processing', 'ready', 'failed', 'deleting')",
    )
    op.add_column("documents", sa.Column("file_name", sa.String(500), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(160), nullable=True))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "documents", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "documents", sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False)
    )
    op.create_index(op.f("ix_documents_enabled"), "documents", ["enabled"])
    op.add_column(
        "documents",
        sa.Column("vector_sync_status", sa.String(20), server_default="synced", nullable=False),
    )
    op.add_column("documents", sa.Column("vector_sync_error", sa.Text(), nullable=True))
    op.create_index(op.f("ix_documents_vector_sync_status"), "documents", ["vector_sync_status"])
    op.create_check_constraint(
        op.f("ck_documents_document_version_positive"), "documents", "version > 0"
    )

    op.create_table(
        "document_revisions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("cleaned_content", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "version", name="uq_document_revisions_document_version"
        ),
    )
    op.create_index(
        op.f("ix_document_revisions_document_id"), "document_revisions", ["document_id"]
    )

    op.drop_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_type"), "ingestion_tasks", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_type"),
        "ingestion_tasks",
        "task_type IN ('ingest_document', 'reindex_document', 'export_knowledge_base', "
        "'reindex_knowledge_base', 'delete_document', 'delete_knowledge_base', "
        "'consistency_repair')",
    )
    op.add_column(
        "ingestion_tasks",
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "ingestion_tasks",
        sa.Column("pause_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.drop_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_status"), "ingestion_tasks", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_status"),
        "ingestion_tasks",
        "status IN ('pending', 'crawling', 'parsing', 'chunking', 'embedding', "
        "'indexing', 'retrying', 'completed', 'failed', 'cancelled', "
        "'partially_completed', 'paused')",
    )
    op.add_column("ingestion_tasks", sa.Column("retry_of_task_id", sa.Uuid(), nullable=True))
    op.add_column(
        "ingestion_tasks", sa.Column("result", sa.JSON(), server_default="{}", nullable=False)
    )
    op.create_index(
        op.f("ix_ingestion_tasks_retry_of_task_id"), "ingestion_tasks", ["retry_of_task_id"]
    )

    op.create_table(
        "retrieval_evaluation_cases",
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("relevant_document_id", sa.Uuid(), nullable=True),
        sa.Column("relevant_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relevant_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relevant_chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retrieval_evaluation_cases_knowledge_base_id"),
        "retrieval_evaluation_cases",
        ["knowledge_base_id"],
    )
    op.create_index(
        op.f("ix_retrieval_evaluation_cases_relevant_document_id"),
        "retrieval_evaluation_cases",
        ["relevant_document_id"],
    )
    op.create_index(
        op.f("ix_retrieval_evaluation_cases_relevant_chunk_id"),
        "retrieval_evaluation_cases",
        ["relevant_chunk_id"],
    )


def downgrade() -> None:
    op.drop_table("retrieval_evaluation_cases")
    op.drop_index(op.f("ix_document_revisions_document_id"), table_name="document_revisions")
    op.drop_table("document_revisions")
    op.drop_index(op.f("ix_ingestion_tasks_retry_of_task_id"), table_name="ingestion_tasks")
    op.drop_column("ingestion_tasks", "result")
    op.drop_column("ingestion_tasks", "retry_of_task_id")
    op.drop_column("ingestion_tasks", "cancel_requested")
    op.drop_column("ingestion_tasks", "pause_requested")
    op.drop_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_status"), "ingestion_tasks", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_status"),
        "ingestion_tasks",
        "status IN ('pending', 'crawling', 'parsing', 'chunking', 'embedding', "
        "'indexing', 'retrying', 'completed', 'failed', 'cancelled', 'partially_completed')",
    )
    op.drop_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_type"), "ingestion_tasks", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_ingestion_tasks_ingestion_task_type"),
        "ingestion_tasks",
        "task_type IN ('ingest_document', 'reindex_document', 'export_knowledge_base')",
    )
    op.drop_constraint(op.f("ck_documents_document_version_positive"), "documents", type_="check")
    op.drop_index(op.f("ix_documents_vector_sync_status"), table_name="documents")
    op.drop_index(op.f("ix_documents_enabled"), table_name="documents")
    op.drop_index(op.f("ix_knowledge_bases_workspace_id"), table_name="knowledge_bases")
    for column in (
        "vector_sync_error",
        "vector_sync_status",
        "version",
        "enabled",
        "indexed_at",
        "mime_type",
        "file_name",
    ):
        op.drop_column("documents", column)
    op.drop_constraint(op.f("ck_documents_document_status"), "documents", type_="check")
    op.create_check_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        "status IN ('pending', 'processing', 'ready', 'failed')",
    )
    op.drop_constraint(
        op.f("ck_knowledge_bases_retrieval_weights_valid"), "knowledge_bases", type_="check"
    )
    op.drop_constraint(
        op.f("ck_knowledge_bases_chunk_strategy_valid"), "knowledge_bases", type_="check"
    )
    op.drop_constraint(
        op.f("ck_knowledge_bases_index_version_positive"), "knowledge_bases", type_="check"
    )
    for column in (
        "last_consistency_report",
        "last_consistency_check_at",
        "reranker_model",
        "score_threshold",
        "keyword_weight",
        "semantic_weight",
        "retrieval_mode",
        "index_version",
        "embedding_signature",
        "embedding_passage_prefix",
        "embedding_query_prefix",
        "embedding_revision",
        "workspace_id",
        "chunk_strategy",
    ):
        op.drop_column("knowledge_bases", column)
    op.drop_constraint(
        op.f("ck_knowledge_bases_knowledge_base_status"), "knowledge_bases", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_knowledge_bases_knowledge_base_status"),
        "knowledge_bases",
        "status IN ('active', 'archived')",
    )
