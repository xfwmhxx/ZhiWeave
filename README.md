# ZhiWeave（织知）

<img src="./frontend/public/zhiweave-logo-v1.png" alt="ZhiWeave Logo" width="88" />

> 把资料织成可检索、可评测、可迁移的知识。

ZhiWeave 是一个面向学习资料的本地 RAG 知识库工作台。项目把 RAG 中最值得展示的“数据生产与检索”部分完整实现出来，而不是先套一个聊天框：网页/文件导入、正文解析、Chunk、Embedding、PostgreSQL 权威数据、Qdrant 索引、混合检索、评测、任务恢复、一致性修复与导出。

LLM 生成层尚未接入，这是当前版本唯一刻意保留的下一阶段。已有功能不需要 OpenAI API Key；Embedding 使用本地模型。

## 版本更新

| 版本 | 日期 | 重点 |
|---|---|---|
| **v0.2.0** | 2026-08-31 | 修复碎行正文与半词 Chunk，加入章节上下文、检索去重、关键词高亮和前后文查看 |
| v0.1.0 | 2026-08-30 | 完成网页/文件入库、E5、Qdrant、混合检索、评测、任务和导出主链路 |

完整的“新增 / 修复 / 旧版本问题 / 升级方式”见 [CHANGELOG.md](./CHANGELOG.md)。

> 从 v0.1.0 升级：网页知识库需要先用原入口重新抓取，让 HTML 经过新版结构化清洗，再执行一次整库蓝绿重建；只点“整库重建”不会重新解析旧 HTML。Markdown、TXT、PDF 可直接重建。

## 当前完成度

```text
网页 / Markdown / TXT / PDF
  → 安全校验与结构化正文解析
  → 边界安全的字符或 Token 切片
  → 标题 + 章节 + 正文的 passage: Embedding
  → PostgreSQL 事务保存权威数据
  → Qdrant Cosine 索引
  → 语义 / BM25 / RRF 混合检索
  → Recall@K / MRR 评测
  → 一致性检查、蓝绿重建、快照与通用 ZIP
```

已经实现：

- 任意公开 HTTP/HTTPS 入口的同域、同父目录抓取；MySQL 教程只是演示数据，不是代码限制。
- `robots.txt`、逐跳 SSRF 校验、私网/保留地址拒绝、响应大小、超时、跳转和页数限制。
- 按标题、段落、列表、代码块和表格抽取 HTML；行内代码不再被拆成逐词碎行，围栏代码块保留原始换行。
- Markdown、TXT、PDF 上传与本地解析，默认单文件上限 20 MB；成功入库后清理临时原文件，删除知识库时清理其上传目录。
- 字符切片与模型 Token 切片；重叠起点对齐完整句子、英文单词与代码围栏，Chunk 同时记录章节标题。
- `intfloat/multilingual-e5-small`，384 维，严格区分 `query:` 与 `passage:` 前缀；默认 revision 固定到 commit `614241f...18b3`。
- Embedding 模型、固定 revision、前缀、维度组成向量空间签名；配置不匹配时拒绝混用旧向量。
- 纯向量、BM25 与加权 RRF 混合检索，支持语言/来源/最低分过滤、轻量术语扩展、相邻 Chunk 去重和可选 CrossEncoder Reranker。
- 检索评测集及 Recall@K、MRR、Hit Rate。
- 文档重抓、重建、停用/启用、异步删除与版本留档。
- Celery 任务暂停、继续、取消、重试、部分完成报告与知识库级并发配额。
- PostgreSQL Chunk 与 Qdrant Point 一致性检查；蓝绿整库重建后原子切换 Collection，旧 Collection 清理失败不会回删已启用的新索引。
- Chunk 级评测目标在重建前解除外键、重建后按文档、序号和内容哈希重新绑定；切片变化时保留文档级目标。
- 通用 ZIP 流式导出与 Qdrant Snapshot；PostgreSQL 备份/恢复脚本。
- API Key、按 Key 映射工作空间、每分钟限流、结构化日志、请求 ID 与 Prometheus `/metrics`。
- React 显式路由工作台和独立图文使用指南；检索证据支持章节定位、关键词高亮、完整 Chunk 与前后文查看。
- Docker Compose、CPU/GPU 覆盖配置与 GitHub Actions 质量门禁。

## 真实验收结果

本机环境：WSL2 Ubuntu 24.04、RTX 4060、Node.js 22.13.0、Python 3.12。

演示入口：<https://www.runoob.com/mysql/mysql-tutorial.html>

| 检查项 | 结果 |
|---|---:|
| 网页文档 | 40 |
| Chunk / Qdrant Point | 355 / 355 |
| Embedding | multilingual-e5-small，384 维 |
| 蓝绿重建 | 成功，索引版本 v1 → v5；v5 使用结构化清洗、章节上下文并验证评测目标重绑定 |
| 双存储一致性 | 355 = 355，模型签名匹配 |
| 语义问题 | MySQL WHERE 子句如何筛选记录？ |
| Top-1 | MySQL WHERE 子句 |
| Top-1 Cosine | 约 0.918 |
| 后端测试 | 37 passed |
| 后端静态检查 | Ruff 通过，Mypy 64 个源码文件通过 |
| 数据库结构自检 | Alembic：No new upgrade operations detected |
| 前端检查 | 0 lint warning，生产构建通过 |
| Compose 静态检查 | CPU/GPU 两份 YAML 均成功解析 |

此外，`backend/scripts/e2e_smoke.py` 已真实跑通：创建临时知识库 → 上传 Markdown → Celery 入库 → 三种检索 → 一致性检查 → ZIP 导出 → 异步删除。它不会使用 mock 替代 PostgreSQL、Redis、Qdrant 或 Worker。

## 架构与数据边界

```mermaid
flowchart LR
    UI[React 工作台] --> API[FastAPI]
    API --> PG[(PostgreSQL)]
    API --> REDIS[(Redis)]
    REDIS --> WORKER[Celery Worker]
    WORKER --> PARSER[网页/文件解析]
    PARSER --> CHUNK[Chunk]
    CHUNK --> EMB[本地 E5]
    WORKER --> PG
    EMB --> QD[(Qdrant)]
    API --> BM25[BM25]
    API --> QD
    BM25 --> RRF[RRF 融合]
    QD --> RRF
    RRF --> UI
    RRF -. 后续 .-> LLM[LLM + 引用回答]
```

- PostgreSQL 是权威事实：知识库配置、原文、清洗正文、Chunk、版本、评测集和任务状态都持久化在这里。
- Qdrant 是可重建索引：只保存向量与检索 Payload；丢失后可从 PostgreSQL 安全重建。
- Redis 只负责消息与短期结果：不能代替 PostgreSQL 的业务任务表。
- 一个知识库对应一个向量空间。修改模型、revision、前缀、维度或切片策略时必须重建。

## 技术栈

| 层级 | 技术 | 职责 |
|---|---|---|
| 前端 | React 19、TypeScript、Vite 8、React Router 8 | 工作台、检索实验、评测和指南 |
| API | FastAPI、Pydantic、SQLAlchemy Async | 校验、权限、业务接口 |
| 任务 | Celery 5.6、Redis | 长任务、控制与重试 |
| 权威数据 | PostgreSQL、Alembic | 事务数据与版本迁移 |
| 向量索引 | Qdrant、Cosine | 向量检索、Payload Filter、Snapshot |
| Embedding | Sentence Transformers、E5 | 中英文混合向量与可选 Reranker |
| 内容处理 | HTTPX、Trafilatura、BeautifulSoup、pypdf | 抓取、正文和文件解析 |
| 可观测性 | JSON Log、Prometheus Client | 请求 ID、指标与依赖健康检查 |
| 部署 | Docker Compose、Nginx、GitHub Actions | 可复现环境与质量门禁 |

## 目录结构

```text
runoob_rag/
├── backend/
│   ├── alembic/versions/             # 数据库迁移
│   ├── scripts/e2e_smoke.py          # 真实跨服务验收
│   ├── src/studyrag_backend/
│   │   ├── api/                      # KB、文档、任务、检索 API
│   │   ├── core/                     # 配置、工作空间、日志、指标
│   │   ├── infrastructure/           # Embedding、Redis、Qdrant
│   │   ├── models/                   # SQLAlchemy 领域模型
│   │   ├── services/                 # 抓取、入库、检索、一致性、导出
│   │   └── workers/                  # Celery 入口
│   └── tests/
├── frontend/                         # React 工作台与使用指南
│   └── src/
│       ├── components/               # 工作台外壳、导入面板与设置弹窗
│       ├── pages/                    # 工作台页面与独立指南页
│       └── workspace/                # 状态控制器、上下文、导航和展示工具
├── ops/                              # PostgreSQL 备份与恢复
├── compose.yaml                      # 完整容器栈
├── compose.gpu.yaml                  # NVIDIA GPU 覆盖配置
├── .env.example                      # Linux / WSL2 / Windows 本地配置示例
└── .env.docker.example               # Docker 密钥示例
```

本仓库不包含本地知识库数据、上传文件、模型权重或个人 Blog 草稿。它们分别由 `/storage/`、`/data/`、`/models/`、`/Blog/` 规则排除。

## 环境与版本

| 依赖 | 建议版本 | 是否必须 |
|---|---:|---|
| Python | 3.12+ | 是 |
| uv | 0.9+ | 是，负责 Python 环境与锁文件 |
| Node.js | 22.13.0 | 是 |
| pnpm | 11.24.0 | 是 |
| PostgreSQL | 16 / 17 | 是，权威业务数据 |
| Redis | 7+ | 是，Celery Broker 与结果后端 |
| Qdrant | 1.18+ | 是，向量索引 |
| NVIDIA CUDA | 可选 | 只影响 Embedding 速度，CPU 可跑完整链路 |

获取源码：

```bash
git clone https://github.com/xfwmhxx/ZhiWeave.git
cd ZhiWeave
```

## Embedding 模型

模型权重不会上传到 GitHub。默认模型是 [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)，384 维，项目固定使用 [revision `614241f...18b3`](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3)。

第一次执行入库或语义检索时，`sentence-transformers` 会自动下载模型到 `storage/models/`。也可以在启动 Worker 前预下载：

```bash
cd backend
uv sync --locked
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', revision='614241f622f53c4eeff9890bdc4f31cfecc418b3', cache_folder='../storage/models')"
```

Windows PowerShell 使用同一条 `uv run python -c` 命令即可。部署机无法联网时，可以提前复制完整的 `storage/models/` 目录；不要把它提交到 Git。修改模型、revision、向量维度或 E5 前缀后，已有知识库必须重新索引。

## 通用初始化

复制环境示例，并至少修改 PostgreSQL 密码：

```bash
cp .env.example .env
```

关键配置如下：

```dotenv
STUDYRAG_DATABASE_URL=postgresql+asyncpg://zhiweave:your-password@127.0.0.1:5432/zhiweave
STUDYRAG_REDIS_URL=redis://127.0.0.1:6379/0
STUDYRAG_CELERY_BROKER_URL=redis://127.0.0.1:6379/1
STUDYRAG_CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
STUDYRAG_QDRANT_URL=http://127.0.0.1:6333
STUDYRAG_EMBEDDING_DEVICE=auto
```

`auto` 会优先使用 CUDA，不可用时自动回退到 CPU。公开部署时还必须设置一个足够长的 `STUDYRAG_API_KEY`。

## 方案一：原生 Linux / Linux 服务器

Ubuntu 24.04 LTS 是推荐环境。先安装基础依赖：

```bash
sudo apt update
sudo apt install -y git curl build-essential postgresql redis-server
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 22.13.0
corepack enable
corepack prepare pnpm@11.24.0 --activate
```

安装 Qdrant Server 时使用 [Qdrant 官方安装文档](https://qdrant.tech/documentation/guides/installation/) 或 [GitHub Releases](https://github.com/qdrant/qdrant/releases)，并让它只监听可信网络。默认地址应为 `http://127.0.0.1:6333`。

创建 PostgreSQL 用户和数据库：

```bash
sudo -u postgres psql
```

```sql
CREATE USER zhiweave WITH PASSWORD 'your-password';
CREATE DATABASE zhiweave OWNER zhiweave;
\q
```

确认三个服务可用后初始化后端：

```bash
sudo systemctl enable --now postgresql redis-server qdrant
cd ZhiWeave
cp .env.example .env
# 编辑 .env 中的数据库密码
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn studyrag_backend.main:app --host 127.0.0.1 --port 8000 --reload
```

另开终端启动 Worker：

```bash
cd ZhiWeave/backend
uv run celery -A studyrag_backend.workers.celery_app:celery_app worker \
  --queues=ingestion,embedding,export,default \
  --concurrency=1 --loglevel=INFO
```

再启动前端：

```bash
cd ZhiWeave/frontend
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1
```

正式 Linux 部署应移除 Uvicorn 的 `--reload`，使用 systemd 或容器管理 API/Worker，并在前面配置 Nginx、HTTPS、防火墙和备份任务。

## 方案二：Windows + WSL2 Ubuntu

这是 Windows 电脑上最推荐的开发方式：浏览器和编辑器留在 Windows，后端、Celery、Redis、PostgreSQL 与 Qdrant 运行在 Ubuntu 中，更接近实际 Linux 服务器。

以管理员身份打开 PowerShell：

```powershell
wsl --install -d Ubuntu-24.04
wsl --set-default-version 2
```

如果发行版没有启用 systemd，在 Ubuntu 的 `/etc/wsl.conf` 写入：

```ini
[boot]
systemd=true
```

随后在 PowerShell 执行 `wsl --shutdown`，重新进入 Ubuntu。接下来的 PostgreSQL、Redis、Qdrant、Python、Node 和启动步骤与“原生 Linux”完全相同。

建议把仓库克隆到 WSL 的 Linux 文件系统，例如 `~/projects/ZhiWeave`，不要长期放在 `/mnt/c` 下运行数据库或大量依赖文件。Windows 浏览器可以直接访问 WSL 暴露的 `localhost:5173` 和 `localhost:8000`。

需要 NVIDIA GPU 时，只在 Windows 安装支持 WSL 的新版 NVIDIA 驱动，然后进入 Ubuntu 执行 `nvidia-smi` 验证；不要在 WSL 中重复安装 Linux 内核显卡驱动。CPU 环境则设置 `STUDYRAG_EMBEDDING_DEVICE=cpu`。

## 方案三：完全原生 Windows

可以用于本地演示，但不是本项目的首选生产方式。Celery 官方不把 Windows 作为正式支持平台，Redis Server 也没有官方原生 Windows 发行版；因此重任务稳定性和环境复现能力不如 Linux/WSL2。

需要准备：

1. Python 3.12、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 22.13.0 与 pnpm 11.24.0。
2. [PostgreSQL Windows 安装包](https://www.postgresql.org/download/windows/)，创建 `zhiweave` 用户和数据库。
3. [Qdrant Windows Release](https://github.com/qdrant/qdrant/releases)，启动 `qdrant.exe` 并监听 `127.0.0.1:6333`。
4. 一个 Redis 协议兼容的 Windows 服务，例如 [Memurai](https://www.memurai.com/)；本地演示也可使用可信的社区 Redis Windows 构建。
5. 将 `.env.example` 复制为 `.env`，使用上面“通用初始化”中的 TCP 地址，不能使用 Linux Unix Socket。

PowerShell 中初始化和启动：

```powershell
Set-Location ZhiWeave\backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn studyrag_backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Windows Worker 必须使用单进程池：

```powershell
Set-Location ZhiWeave\backend
uv run celery -A studyrag_backend.workers.celery_app:celery_app worker `
  --pool=solo --queues=ingestion,embedding,export,default `
  --concurrency=1 --loglevel=INFO
```

前端：

```powershell
Set-Location ZhiWeave\frontend
pnpm install --frozen-lockfile
pnpm dev --host 127.0.0.1
```

如果 Windows 原生 Celery、Redis 或 Qdrant 出现兼容性问题，应切换到 WSL2，而不是在业务代码中加入平台专用补丁。

## 启动后的地址

- 前端：<http://localhost:5173>
- OpenAPI：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/v1/health/ready>
- Prometheus 指标：<http://localhost:8000/metrics>

## Docker Compose 部署

Docker Compose 是最容易复现的整套部署方式，也是服务器部署的推荐起点。首次启动时模型会下载到被持久化且不进入 Git 的 `model_cache` Volume。

```bash
cp .env.docker.example .env.docker
# 修改 POSTGRES_PASSWORD 和 STUDYRAG_API_KEY
docker compose --env-file .env.docker up --build -d
```

需要 NVIDIA Container Toolkit 时叠加 GPU 配置：

```bash
docker compose --env-file .env.docker \
  -f compose.yaml -f compose.gpu.yaml up --build -d
```

容器中的 API 默认启用 Key。点击前端右上角 `⌘` 输入同一个 Key。生产环境不要使用示例默认值。

## 主要 API

| 能力 | 代表路径 |
|---|---|
| 知识库 CRUD | `GET/POST /api/v1/knowledge-bases`、`PATCH/DELETE /{id}` |
| 网页/文件入库 | `POST /{id}/imports/web`、`POST /{id}/imports/files` |
| 文档管理 | `PATCH/DELETE /{id}/documents/{document_id}` |
| 停用/启用/重抓/重建 | `POST /documents/{document_id}/{action}` |
| Chunk 查看 | `GET /{id}/chunks` |
| 任务控制 | `POST /{id}/tasks/{task_id}/{pause|resume|cancel|retry}` |
| 三种检索 | `POST /{id}/search`，`mode=semantic|keyword|hybrid` |
| 检索评测 | `POST /{id}/evaluation-cases`、`POST /{id}/evaluation-runs` |
| 整库蓝绿重建 | `POST /{id}/reindex` |
| 一致性与修复 | `GET /{id}/consistency`、`POST /{id}/consistency/repair` |
| 通用导出/快照 | `GET /{id}/export`、`POST /{id}/snapshots` |

## 导出与恢复

通用 ZIP 是可审查、跨向量数据库的交换格式：

```text
zhiweave-<knowledge-base-id>.zip
├── manifest.json
├── sources.jsonl
├── chunks.jsonl
├── documents/*.md
├── examples/rebuild_and_search.py
├── requirements.txt
└── README.md
```

Qdrant Snapshot 更适合同版本 Qdrant 的精确恢复；通用 ZIP 更适合分享、面试演示或迁移到 Chroma/pgvector。PostgreSQL 备份与恢复使用 `ops/backup-postgres.sh` 和 `ops/restore-postgres.sh`。

## 配置与安全

本地开发默认不要求 Key；部署时至少设置：

```dotenv
STUDYRAG_API_KEY=replace-with-a-long-random-value
```

多工作空间可以配置 JSON 映射：

```dotenv
STUDYRAG_WORKSPACE_API_KEYS={"alice":"key-a","bob":"key-b"}
```

每个请求由 Key 解析出工作空间，知识库查询必须带 `workspace_id` 条件。前端只把用户输入的 Key 存在浏览器 localStorage；任何第三方 LLM Key 将来仍必须由后端保存，不能打进 React Bundle。

## 开发验证

```bash
cd ZhiWeave/backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
uv run alembic check
uv run python scripts/e2e_smoke.py

cd ../frontend
pnpm lint
pnpm build
```

## 当前边界与下一阶段

尚未完成的不是“知识库主链路”，而是生成层：

1. Ollama/OpenAI 兼容 Provider。
2. 检索结果上下文组装、引用定位与无依据拒答。
3. 面向生成答案的端到端 RAG 评测。
4. 可选 Chroma Adapter，用同一接口比较嵌入式与服务型向量数据库。
