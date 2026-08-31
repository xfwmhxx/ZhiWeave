# ZhiWeave Backend

FastAPI + PostgreSQL + Celery + Redis + Qdrant 的本地 RAG 知识库后端。Python 3.12 依赖由 uv 与 `uv.lock` 管理。

## 当前能力

- PostgreSQL、Redis、Qdrant 并发就绪检查。
- 知识库、文档、Chunk 和入库任务模型。
- 同域同目录网页抓取、`robots.txt`、正文抽取与 SSRF 防护。
- 480/80 默认字符切片、偏移、SHA-256 和确定性向量 Point ID。
- `multilingual-e5-small` GPU Embedding，384 维、归一化向量和 E5 前缀。
- Qdrant Collection、Payload 索引、幂等重建和 Top-K 检索。
- Celery 网页入库任务与 PostgreSQL 业务进度。
- 可移植 ZIP 导出与重建示例。
- Ruff、Mypy、Alembic check 和 Pytest。

## 启动

```bash
cd ZhiWeave/backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn studyrag_backend.main:app --host 127.0.0.1 --port 8000 --reload
```

另开一个终端：

```bash
cd ZhiWeave/backend
uv run celery \
  -A studyrag_backend.workers.celery_app:celery_app worker \
  --queues=ingestion,embedding,export,default \
  --concurrency=1 \
  --loglevel=INFO
```

启动前先把仓库根目录的 `.env.example` 复制为 `.env`，并配置独立的 PostgreSQL 用户、密码和数据库。跨平台安装、模型下载和部署方式见根目录 `README.md`。

## 检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic check
uv run pytest --cov --cov-report=term-missing
```

## 数据一致性

- PostgreSQL 是原文、Chunk 和任务的权威事实。
- Qdrant 是可从 PostgreSQL 或导出 ZIP 重建的检索索引。
- `knowledge_base_id + canonical_uri` 防止同一网页重复建档。
- Chunk 使用内容哈希，Qdrant Point ID 由文档、序号和哈希确定性生成。
- 同一 URL 内容或标题变化时覆盖旧 Chunk 和旧向量；不变时跳过重复索引。

## 本地服务

```bash
systemctl is-active postgresql redis-server qdrant
curl http://127.0.0.1:6333/healthz
```

Qdrant 的可复用服务文件位于 `../ops/systemd/qdrant.service`，只绑定 `127.0.0.1`。
