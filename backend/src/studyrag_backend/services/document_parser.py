from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from studyrag_backend.models.enums import DocumentSourceType
from studyrag_backend.services.web_crawler import normalize_content

SUPPORTED_UPLOAD_TYPES: dict[str, DocumentSourceType] = {
    ".md": DocumentSourceType.MARKDOWN,
    ".markdown": DocumentSourceType.MARKDOWN,
    ".txt": DocumentSourceType.PLAIN_TEXT,
    ".pdf": DocumentSourceType.PDF,
}


@dataclass(frozen=True, slots=True)
class SourceDocument:
    title: str
    content: str
    source_type: DocumentSourceType
    source_uri: str | None
    canonical_uri: str
    language: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _read_text(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("text file encoding is not UTF-8 or GB18030")


def parse_uploaded_document(
    path: Path,
    *,
    file_name: str,
    mime_type: str | None,
    canonical_uri: str,
) -> SourceDocument:
    suffix = path.suffix.lower()
    source_type = SUPPORTED_UPLOAD_TYPES.get(suffix)
    if source_type is None:
        raise ValueError("only Markdown, plain text, and PDF files are supported")

    metadata: dict[str, Any] = {"source_kind": "upload", "extension": suffix}
    title = Path(file_name).stem
    if source_type == DocumentSourceType.PDF:
        reader = PdfReader(path)
        page_texts = [page.extract_text() or "" for page in reader.pages]
        content = normalize_content("\n\n".join(page_texts))
        pdf_title = getattr(reader.metadata, "title", None) if reader.metadata else None
        if pdf_title:
            title = str(pdf_title).strip()
        metadata["page_count"] = len(reader.pages)
    else:
        content = normalize_content(_read_text(path))

    if not content:
        raise ValueError("document did not contain extractable text")
    return SourceDocument(
        title=title[:500],
        content=content,
        source_type=source_type,
        source_uri=None,
        canonical_uri=canonical_uri,
        file_name=file_name[:500],
        mime_type=(mime_type or "application/octet-stream")[:160],
        metadata=metadata,
    )
