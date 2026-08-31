import json
import re
from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile

from studyrag_backend.models.chunk import Chunk
from studyrag_backend.models.document import Document
from studyrag_backend.models.knowledge_base import KnowledgeBase

_UNSAFE_FILENAME = re.compile(r"[^a-zA-Z0-9_-]+")


def _document_filename(index: int, document: Document) -> str:
    tail = (document.canonical_uri or document.source_uri or "document").rstrip("/").split("/")[-1]
    stem = tail.rsplit(".", 1)[0]
    safe_stem = _UNSAFE_FILENAME.sub("-", stem).strip("-")[:80] or "document"
    return f"documents/{index:03d}-{safe_stem}.md"


def _rebuild_example(
    collection_name: str,
    model_name: str,
    model_revision: str,
    dimension: int,
    query_prefix: str,
    passage_prefix: str,
) -> str:
    return f'''"""Rebuild the exported ZhiWeave collection and run one semantic search."""
import json
from pathlib import Path

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "{collection_name}"
MODEL_NAME = "{model_name}"
MODEL_REVISION = "{model_revision}"
DIMENSION = {dimension}
QUERY_PREFIX = {query_prefix!r}
PASSAGE_PREFIX = {passage_prefix!r}

client = QdrantClient(url="http://127.0.0.1:6333")
model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
chunks_path = ROOT / "chunks.jsonl"
chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()]

if not client.collection_exists(COLLECTION):
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=DIMENSION, distance=models.Distance.COSINE),
    )

vectors = model.encode(
    [f"{{PASSAGE_PREFIX}}{{item['content']}}" for item in chunks],
    normalize_embeddings=True,
).tolist()
client.upsert(
    collection_name=COLLECTION,
    points=[
        models.PointStruct(id=index, vector=vector, payload=item)
        for index, (item, vector) in enumerate(zip(chunks, vectors, strict=True))
    ],
    wait=True,
)

query = "请概括这套资料的核心知识点"
query_vector = model.encode([f"{{QUERY_PREFIX}}{{query}}"], normalize_embeddings=True)[0].tolist()
for point in client.query_points(COLLECTION, query=query_vector, limit=5).points:
    print(round(point.score, 4), point.payload.get("title"), point.payload.get("source_uri"))
'''


def build_portable_export(
    knowledge_base: KnowledgeBase,
    documents: list[Document],
    chunks: list[Chunk],
) -> bytes:
    buffer = BytesIO()
    write_portable_export(buffer, knowledge_base, documents, chunks)
    return buffer.getvalue()


def write_portable_export(
    target: BinaryIO,
    knowledge_base: KnowledgeBase,
    documents: list[Document],
    chunks: list[Chunk],
) -> None:
    document_by_id = {document.id: document for document in documents}
    manifest = {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "knowledge_base": {
            "id": str(knowledge_base.id),
            "workspace_id": knowledge_base.workspace_id,
            "name": knowledge_base.name,
            "description": knowledge_base.description,
            "embedding_model": knowledge_base.embedding_model,
            "embedding_revision": knowledge_base.embedding_revision,
            "embedding_dimension": knowledge_base.embedding_dimension,
            "embedding_query_prefix": knowledge_base.embedding_query_prefix,
            "embedding_passage_prefix": knowledge_base.embedding_passage_prefix,
            "embedding_signature": knowledge_base.embedding_signature,
            "chunk_size": knowledge_base.chunk_size,
            "chunk_overlap": knowledge_base.chunk_overlap,
            "chunk_strategy": knowledge_base.chunk_strategy,
            "distance": "Cosine",
            "source_document_count": len(documents),
            "chunk_count": len(chunks),
        },
        "contents": [
            "documents/*.md",
            "sources.jsonl",
            "chunks.jsonl",
            "examples/rebuild_and_search.py",
            "requirements.txt",
        ],
    }

    with ZipFile(target, mode="w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        source_lines: list[str] = []
        for index, document in enumerate(documents, start=1):
            source_lines.append(
                json.dumps(
                    {
                        "document_id": str(document.id),
                        "title": document.title,
                        "source_uri": document.source_uri,
                        "canonical_uri": document.canonical_uri,
                        "language": document.language,
                        "content_hash": document.content_hash,
                        "fetched_at": (
                            document.fetched_at.isoformat() if document.fetched_at else None
                        ),
                        "enabled": document.enabled,
                    },
                    ensure_ascii=False,
                )
            )
            markdown = (
                f"# {document.title}\n\n"
                f"> 来源: {document.source_uri or 'unknown'}\n\n"
                f"{document.cleaned_content or ''}\n"
            )
            archive.writestr(_document_filename(index, document), markdown)
        archive.writestr("sources.jsonl", "\n".join(source_lines) + "\n")

        chunk_lines: list[str] = []
        for chunk in chunks:
            source_document = document_by_id.get(chunk.document_id)
            chunk_lines.append(
                json.dumps(
                    {
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "sequence_index": chunk.sequence_index,
                        "content": chunk.content,
                        "content_hash": chunk.content_hash,
                        "start_offset": chunk.start_offset,
                        "end_offset": chunk.end_offset,
                        "title": source_document.title if source_document else None,
                        "source_uri": source_document.source_uri if source_document else None,
                    },
                    ensure_ascii=False,
                )
            )
        archive.writestr("chunks.jsonl", "\n".join(chunk_lines) + "\n")
        archive.writestr(
            "examples/rebuild_and_search.py",
            _rebuild_example(
                knowledge_base.vector_collection_name,
                knowledge_base.embedding_model,
                knowledge_base.embedding_revision,
                knowledge_base.embedding_dimension,
                knowledge_base.embedding_query_prefix,
                knowledge_base.embedding_passage_prefix,
            ),
        )
        archive.writestr(
            "requirements.txt",
            "qdrant-client>=1.19.0\nsentence-transformers>=6.0.0\n",
        )
        archive.writestr(
            "README.md",
            "# ZhiWeave portable export\n\n"
            "This archive contains cleaned source documents and deterministic chunks. "
            "Start Qdrant locally, install `requirements.txt`, then run "
            "`python examples/rebuild_and_search.py` to rebuild the vectors.\n",
        )
