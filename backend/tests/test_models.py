from sqlalchemy import CheckConstraint, String, UniqueConstraint

import studyrag_backend.models  # noqa: F401
from studyrag_backend.db.base import Base


def test_expected_domain_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "knowledge_bases",
        "documents",
        "document_revisions",
        "chunks",
        "ingestion_tasks",
        "retrieval_evaluation_cases",
    }


def test_business_invariants_exist_in_metadata() -> None:
    chunks = Base.metadata.tables["chunks"]
    documents = Base.metadata.tables["documents"]
    knowledge_bases = Base.metadata.tables["knowledge_bases"]
    tasks = Base.metadata.tables["ingestion_tasks"]

    assert any(isinstance(item, UniqueConstraint) for item in chunks.constraints)
    assert any(isinstance(item, UniqueConstraint) for item in documents.constraints)
    assert any(isinstance(item, CheckConstraint) for item in knowledge_bases.constraints)
    assert any(isinstance(item, CheckConstraint) for item in tasks.constraints)


def test_non_native_enum_storage_lengths_match_migrations() -> None:
    documents = Base.metadata.tables["documents"]
    knowledge_bases = Base.metadata.tables["knowledge_bases"]
    tasks = Base.metadata.tables["ingestion_tasks"]

    vector_sync_type = documents.c.vector_sync_status.type
    retrieval_mode_type = knowledge_bases.c.retrieval_mode.type
    task_type = tasks.c.task_type.type

    assert isinstance(vector_sync_type, String)
    assert isinstance(retrieval_mode_type, String)
    assert isinstance(task_type, String)
    assert vector_sync_type.length == 20
    assert retrieval_mode_type.length == 20
    assert task_type.length == 40
