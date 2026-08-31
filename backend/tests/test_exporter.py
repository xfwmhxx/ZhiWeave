import json
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.enums import DocumentSourceType, DocumentStatus
from studyrag_backend.models.knowledge_base import KnowledgeBase
from studyrag_backend.services.exporter import build_portable_export


def test_portable_export_contains_sources_chunks_and_rebuild_example() -> None:
    knowledge_base_id = uuid4()
    document_id = uuid4()
    knowledge_base = KnowledgeBase(
        id=knowledge_base_id,
        name="MySQL 学习库",
        description="测试导出",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_revision="main",
        embedding_dimension=384,
        embedding_query_prefix="query: ",
        embedding_passage_prefix="passage: ",
        embedding_signature="a" * 64,
        chunk_size=480,
        chunk_overlap=80,
        chunk_strategy="character",
        workspace_id="local",
        vector_collection_name=f"studyrag_{knowledge_base_id.hex}",
    )
    document = Document(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        source_type=DocumentSourceType.WEB_PAGE,
        status=DocumentStatus.READY,
        title="MySQL WHERE 子句",
        source_uri="https://www.runoob.com/mysql/mysql-where-clause.html",
        canonical_uri="https://www.runoob.com/mysql/mysql-where-clause.html",
        content_hash="a" * 64,
        cleaned_content="WHERE 子句用于筛选记录。",
    )
    chunk = Chunk(
        id=uuid4(),
        document_id=document_id,
        sequence_index=0,
        content="WHERE 子句用于筛选记录。",
        content_hash="b" * 64,
        character_count=14,
        vector_point_id=uuid4(),
        start_offset=0,
        end_offset=14,
    )

    archive_bytes = build_portable_export(knowledge_base, [document], [chunk])

    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "chunks.jsonl" in names
        assert "sources.jsonl" in names
        assert "examples/rebuild_and_search.py" in names
        assert any(name.startswith("documents/001-") for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["knowledge_base"]["embedding_dimension"] == 384
        assert manifest["knowledge_base"]["embedding_signature"] == "a" * 64
        assert manifest["knowledge_base"]["chunk_count"] == 1
        exported_chunk = json.loads(archive.read("chunks.jsonl").decode().strip())
        assert exported_chunk["title"] == "MySQL WHERE 子句"
        assert "passage:" in archive.read("examples/rebuild_and_search.py").decode()
