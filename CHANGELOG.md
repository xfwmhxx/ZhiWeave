# ZhiWeave 更新日志

本文件记录每个版本新增了什么、修复了什么，以及旧版本升级时需要注意什么。版本号遵循语义化版本。

## [Unreleased]

- 预留给下一阶段的可选 LLM 生成、引用与拒答链路。

## [0.2.0] - 2026-08-31

### 修复

- 修复网页行内标签被强制换行的问题。旧版可能把 `cursor.execute(sql, values)` 清洗成逐词、逐符号碎行，导致 Chunk 和检索证据难以阅读。
- 修复字符重叠直接从固定偏移开始的问题。旧版 Chunk 可能以 `calhost`、`xcept` 等半个英文单词开头。
- 修复 Chunk 在 Markdown 围栏代码块内部开始的问题；短代码块会尽量保持完整边界。
- 检索时以 PostgreSQL 为权威来源，不再把 Qdrant 中可能残留的孤儿 Payload 当成可返回正文。
- 抑制同一文档相邻或明显重叠的 Chunk 同时挤占 Top-K。

### 新增

- HTML 按标题、段落、列表、代码块和表格进行结构化抽取，代码缩进与块间空行得到保留。
- Chunk 记录最近章节标题；Embedding 使用“文档标题 + 章节标题 + Chunk 正文”，展示仍使用干净原文。
- 检索结果新增章节路径、Chunk 序号、字符数、关键词高亮、完整内容展开和相邻 Chunk 上下文。
- 新增 `GET /api/v1/knowledge-bases/{id}/chunks/{chunk_id}/context` 上下文接口。
- 新增本更新日志，并在 README 提供最近版本摘要与升级步骤。

### 性能与行为变化

- 纯语义检索改为先查询 Qdrant，再按命中的 Chunk ID 批量读取 PostgreSQL，不再预先加载整个知识库全部 Chunk。
- MySQL 演示库经重新抓取和蓝绿重建后由 407 个噪声较多的 Chunk 调整为 355 个结构化 Chunk，PostgreSQL 与 Qdrant 数量一致。
- 实测问题“MySQL WHERE 子句如何筛选记录？”在新索引上的最高 Cosine 约为 0.918。

### 从 0.1.0 升级

旧 Document 的 `cleaned_content` 已经包含旧清洗结果，只执行“整库重建”不会重新解析 HTML。网页知识库应先用原入口重新抓取，再执行一次整库蓝绿重建；本地 Markdown、TXT、PDF 不需要重新抓取，但建议重建以获得标题/章节上下文向量。

## [0.1.0] - 2026-08-30

### 初始版本

- 完成 FastAPI、Celery、Redis、PostgreSQL、Qdrant 与本地 E5 的完整检索链路。
- 支持网页/文件入库、字符/Token Chunk、语义/BM25/RRF 检索、评测、一致性检查、蓝绿重建、导出和快照。
- 完成 React 工作台、显式路由和独立图文使用指南。

