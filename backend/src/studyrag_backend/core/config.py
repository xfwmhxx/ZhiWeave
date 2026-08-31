from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_EMBEDDING_MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


class Settings(BaseSettings):
    """Environment-backed settings shared by the API and Celery workers."""

    model_config = SettingsConfigDict(
        env_prefix="STUDYRAG_",
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ZhiWeave API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Local development uses PostgreSQL peer authentication for the Linux user `hina`.
    database_url: str = "postgresql+asyncpg:///studyrag?host=/var/run/postgresql"
    database_echo: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    # Pin the exact Hugging Face commit so one signature always maps to one vector space.
    embedding_model_revision: str = DEFAULT_EMBEDDING_MODEL_REVISION
    embedding_dimension: int = Field(default=384, gt=0)
    embedding_query_prefix: str = "query: "
    embedding_passage_prefix: str = "passage: "
    embedding_device: Literal["auto", "cpu", "cuda"] = "auto"
    embedding_batch_size: int = Field(default=32, gt=0, le=256)
    model_cache_dir: Path = PROJECT_ROOT / "storage" / "models"

    chunk_size: int = Field(default=480, ge=100, le=2000)
    chunk_overlap: int = Field(default=80, ge=0, le=500)
    chunk_strategy: Literal["character", "token"] = "character"
    crawler_user_agent: str = "ZhiWeave/0.1 (+local educational RAG project)"
    crawler_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    crawler_max_response_bytes: int = Field(default=2_000_000, ge=100_000, le=20_000_000)
    crawler_max_redirects: int = Field(default=5, ge=0, le=10)
    crawler_default_max_pages: int = Field(default=40, ge=1, le=100)
    crawler_delay_seconds: float = Field(default=0.6, ge=0, le=10)
    # Some local TUN proxies use a reserved "fake IP" range for public DNS names.
    # Keep this empty unless the local resolver is known and trusted.
    crawler_trusted_dns_proxy_cidrs: list[str] = Field(default_factory=list)

    # Local development stays passwordless by default. Set this value in hosted environments.
    api_key: str | None = None
    default_workspace_id: str = "local"
    workspace_api_keys: dict[str, str] = Field(default_factory=dict)
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10_000)
    max_active_tasks_per_knowledge_base: int = Field(default=3, ge=1, le=50)
    max_documents_per_knowledge_base: int = Field(default=10_000, ge=1, le=1_000_000)
    max_upload_bytes: int = Field(default=20_000_000, ge=100_000, le=200_000_000)
    upload_dir: Path = PROJECT_ROOT / "storage" / "uploads"
    export_spool_bytes: int = Field(default=8_000_000, ge=1_000_000, le=100_000_000)
    reranker_model_name: str | None = None
    retrieval_candidate_limit: int = Field(default=100, ge=20, le=1000)
    metrics_enabled: bool = True

    @field_validator("api_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        normalized = f"/{value.strip('/')}"
        return normalized if normalized != "/" else ""

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_chunking(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
