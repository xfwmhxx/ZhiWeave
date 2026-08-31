from enum import Enum, StrEnum


def enum_values(enum_type: type[Enum]) -> list[str]:
    """Persist stable API values instead of Python member names."""
    return [str(member.value) for member in enum_type]


class KnowledgeBaseStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETING = "deleting"
    FAILED = "failed"


class RetrievalMode(StrEnum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class VectorSyncStatus(StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    ERROR = "error"


class DocumentSourceType(StrEnum):
    MARKDOWN = "markdown"
    WEB_PAGE = "web_page"
    PDF = "pdf"
    PLAIN_TEXT = "plain_text"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"


class IngestionTaskType(StrEnum):
    INGEST_DOCUMENT = "ingest_document"
    REINDEX_DOCUMENT = "reindex_document"
    EXPORT_KNOWLEDGE_BASE = "export_knowledge_base"
    REINDEX_KNOWLEDGE_BASE = "reindex_knowledge_base"
    DELETE_DOCUMENT = "delete_document"
    DELETE_KNOWLEDGE_BASE = "delete_knowledge_base"
    CONSISTENCY_REPAIR = "consistency_repair"


class IngestionTaskStatus(StrEnum):
    PENDING = "pending"
    CRAWLING = "crawling"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    RETRYING = "retrying"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"
