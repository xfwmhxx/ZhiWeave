from pathlib import Path

from studyrag_backend.models.enums import DocumentSourceType
from studyrag_backend.services.document_parser import parse_uploaded_document


def test_parse_markdown_upload_normalizes_text(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("# RAG\n\n\n向量   检索", encoding="utf-8")

    document = parse_uploaded_document(
        source,
        file_name="学习笔记.md",
        mime_type="text/markdown",
        canonical_uri="upload://local/notes",
    )

    assert document.source_type == DocumentSourceType.MARKDOWN
    assert document.title == "学习笔记"
    assert document.content == "# RAG\n\n向量 检索"
