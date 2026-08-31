import { ImportPanel } from '../components/ImportPanel'
import { RetrievalResultCard } from '../components/RetrievalResultCard'
import { useWorkspace } from '../workspace/context'
import {
  formatTime,
  isResolvedHistoricalFailure,
  taskLabels,
  terminalTaskStates,
} from '../workspace/presentation'

export function OverviewPage() {
  const { activeKb, latestTask, documents, importMode, crawlScope, navigateTo } = useWorkspace()
  const pipeline = [
    ['资料读取', importMode === 'web' ? `同域 ${crawlScope.prefix}` : 'Markdown / TXT / PDF', ['crawling']],
    ['正文清洗', '提取并规范化正文', ['parsing']],
    ['文本切片', `${activeKb?.chunk_size ?? 480} ${activeKb?.chunk_strategy === 'token' ? 'Token' : '字符'} · 重叠 ${activeKb?.chunk_overlap ?? 80}`, ['chunking']],
    ['向量化', activeKb?.embedding_model ?? 'multilingual-e5-small', ['embedding']],
    ['写入 Qdrant', `Cosine · ${activeKb?.embedding_dimension ?? 384} 维`, ['indexing', 'completed']],
  ] as const
  const taskStageIndex = latestTask ? pipeline.findIndex((step) => step[2].includes(latestTask.status as never)) : -1

  return <>
    <section className="stats-grid" aria-label="知识库统计">
      <article className="stat-card"><span className="stat-label">文档</span><strong>{activeKb?.document_count ?? 0}</strong><small>{activeKb ? '已保存来源页面' : '等待创建知识库'}</small></article>
      <article className="stat-card"><span className="stat-label">Chunks</span><strong>{activeKb?.chunk_count ?? 0}</strong><small>每段最多 {activeKb?.chunk_size ?? 480} {activeKb?.chunk_strategy === 'token' ? 'Token' : '字符'}</small></article>
      <article className="stat-card accent-stat"><span className="stat-label">Embedding</span><strong>{activeKb?.embedding_dimension ?? 384} <em>维</em></strong><small>{activeKb?.embedding_model ?? 'multilingual-e5-small'}</small></article>
      <article className="stat-card"><span className="stat-label">任务</span><strong>{activeKb?.active_task_count ?? 0}</strong><small>{latestTask ? taskLabels[latestTask.status] ?? latestTask.status : '当前无任务'}</small></article>
    </section>
    <section className="workspace-grid">
      <ImportPanel />
      <article className="panel pipeline-panel">
        <div className="panel-heading compact"><div><span className="panel-kicker">LIVE PIPELINE</span><h2>处理流水线</h2></div><span className="queue-label">Celery 队列</span></div>
        <div className="pipeline-list">{pipeline.map((step, index) => {
          const done = latestTask?.status === 'completed' || taskStageIndex > index
          const active = taskStageIndex === index && latestTask?.status !== 'completed'
          return <div className={`pipeline-step ${done ? 'done' : active ? 'active' : 'waiting'}`} key={step[0]}><span className="step-marker">{done ? '✓' : String(index + 1).padStart(2, '0')}</span><span className="step-copy"><strong>{step[0]}</strong><small>{step[1]}</small></span>{active && <span className="working">{latestTask?.progress}%</span>}</div>
        })}</div>
      </article>
    </section>
    <section className="bottom-grid">
      <article className="panel empty-state"><span className="empty-icon">▧</span><div><h3>{documents[0]?.title ?? '还没有已索引的文档'}</h3><p>{documents.length ? `最近抓取于 ${formatTime(documents[0].fetched_at)}，当前共 ${documents.length} 个页面。` : '首次任务完成后，这里会显示每个页面的状态、Chunk 数量和原始来源。'}</p></div><button onClick={() => navigateTo('sources')} type="button">查看数据源</button></article>
      <article className="tip-card"><span>为什么暂时没有聊天框？</span><p>当前阶段专注于可验证的“检索”链路。接入大模型只是后续可选的生成层，不影响知识库先跑通。</p></article>
    </section>
  </>
}

export function SourcesPage() {
  const { documents, busy, documentAction, toggleDocument, workspaceLoading } = useWorkspace()
  return <div className="section-stack">
    <ImportPanel />
    <article className="panel data-panel">
      <div className="section-title"><div><span className="panel-kicker">DOCUMENTS</span><h2>知识来源</h2></div><span>{documents.length} 项</span></div>
      {workspaceLoading ? <p className="panel-empty">正在读取知识来源…</p> : documents.length ? <div className="data-list">{documents.map((doc) => <div className={`data-row document-row ${doc.enabled ? '' : 'document-disabled'}`} key={doc.id}>
        <span className={`doc-status ${doc.enabled ? doc.status : 'disabled'}`} />
        <div className="document-copy">
          <strong>{doc.title}{!doc.enabled && <em className="disabled-badge">已停用</em>}</strong>
          {doc.source_uri ? <a href={doc.source_uri} target="_blank" rel="noreferrer">{doc.source_uri}</a> : <small>{doc.file_name ?? doc.canonical_uri}</small>}
          <small>v{doc.version} · {doc.source_type} · 向量 {doc.vector_sync_status}</small>
        </div>
        <span>{doc.language ?? '未知语言'}</span><time>{formatTime(doc.fetched_at)}</time>
        <div className="row-actions">
          <button disabled={busy.includes(doc.id)} onClick={() => toggleDocument(doc.id, doc.enabled)} type="button">{doc.enabled ? '停用' : '启用'}</button>
          <button disabled={busy.includes(doc.id) || !doc.enabled} onClick={() => documentAction(doc.id, 'refetch')} type="button">{doc.source_type === 'web_page' ? '重抓' : '重建'}</button>
          <button disabled={busy.includes(doc.id) || !doc.enabled} onClick={() => documentAction(doc.id, 'reindex')} type="button">重建索引</button>
          <button className="danger-text" disabled={busy.includes(doc.id)} onClick={() => documentAction(doc.id, 'delete')} type="button">删除</button>
        </div>
      </div>)}</div> : <p className="panel-empty">还没有数据源，可以抓取网页或上传本地文档。</p>}
    </article>
  </div>
}

export function ChunksPage() {
  const { chunks, workspaceLoading } = useWorkspace()
  return <article className="panel data-panel">
    <div className="section-title"><div><span className="panel-kicker">CHUNK EXPLORER</span><h2>Chunk 工作台</h2></div><span>显示前 {chunks.length} 条</span></div>
    {workspaceLoading ? <p className="panel-empty">正在读取 Chunk…</p> : chunks.length ? <div className="chunk-list">{chunks.map((chunk) => <article className="chunk-card" key={chunk.id}><header><b>#{chunk.sequence_index + 1}</b><span>{chunk.character_count} 字符</span><code>{chunk.content_hash.slice(0, 10)}</code></header>{chunk.extra_metadata.section_heading && <div className="chunk-heading">{chunk.extra_metadata.section_heading}</div>}<pre>{chunk.content}</pre><footer>{chunk.extra_metadata.title ?? chunk.document_id}</footer></article>)}</div> : <p className="panel-empty">完成一次网页入库后，可在这里检查切片边界、重叠与内容哈希。</p>}
  </article>
}

export function RetrievalPage() {
  const workspace = useWorkspace()
  const {
    query, setQuery, searchMode, setSearchMode, topK, setTopK, scoreThreshold,
    setScoreThreshold, languageFilter, setLanguageFilter, sourceTypeFilter,
    setSourceTypeFilter, expandQuery, setExpandQuery, useReranker, setUseReranker,
    runSearch, activeId, busy, hits, evaluationCases, evaluationReport, documents,
    evaluationQuery, setEvaluationQuery, evaluationDocumentId, setEvaluationDocumentId,
    addEvaluationCase, runEvaluation,
  } = workspace
  return <div className="section-stack">
    <div className="retrieval-layout">
      <article className="panel retrieval-query">
        <span className="panel-kicker">HYBRID RETRIEVAL</span><h2>检索实验室</h2>
        <p>可对比纯向量、关键词 BM25 与 RRF 混合检索；仍然不调用聊天模型。</p>
        <form onSubmit={runSearch}>
          <label className="sr-only" htmlFor="retrieval-query">检索问题</label>
          <textarea id="retrieval-query" value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="retrieval-controls">
            <label>检索方式<select value={searchMode} onChange={(event) => setSearchMode(event.target.value as typeof searchMode)}><option value="hybrid">混合 RRF</option><option value="semantic">纯向量</option><option value="keyword">关键词 BM25</option></select></label>
            <label>Top-K<input max="20" min="1" onChange={(event) => setTopK(Number(event.target.value))} type="number" value={topK} /></label>
            <label>向量最低分<input max="1" min="0" onChange={(event) => setScoreThreshold(event.target.value)} placeholder="自动" step="0.05" type="number" value={scoreThreshold} /></label>
            <label>语言<input onChange={(event) => setLanguageFilter(event.target.value)} placeholder="zh-CN" value={languageFilter} /></label>
            <label>来源<select value={sourceTypeFilter} onChange={(event) => setSourceTypeFilter(event.target.value)}><option value="">全部</option><option value="web_page">网页</option><option value="markdown">Markdown</option><option value="plain_text">TXT</option><option value="pdf">PDF</option></select></label>
            <label className="check-control"><input checked={expandQuery} onChange={(event) => setExpandQuery(event.target.checked)} type="checkbox" />中英文术语扩展</label>
            <label className="check-control"><input checked={useReranker} onChange={(event) => setUseReranker(event.target.checked)} type="checkbox" />使用重排模型</label>
          </div>
          <button className="primary-button" disabled={!activeId || busy === 'search'} type="submit">{busy === 'search' ? '检索中…' : '运行检索'}</button>
        </form>
      </article>
      <div className="search-results">
        <div className="retrieval-evidence-note"><b>检索证据</b><span>以下是数据库中的原始 Chunk，不是大模型整理后的最终回答。</span></div>
        {hits.length ? hits.map((hit, index) => <RetrievalResultCard activeId={activeId} hit={hit} index={index} key={hit.chunk_id} query={query} />) : <article className="panel panel-empty">入库完成后，输入一个中英文混合问题来观察召回结果。</article>}
      </div>
    </div>
    <article className="panel evaluation-panel">
      <div className="section-title"><div><span className="panel-kicker">RETRIEVAL EVALUATION</span><h2>检索评测集</h2></div><button className="secondary-button" disabled={!evaluationCases.length || busy === 'evaluation-run'} onClick={runEvaluation} type="button">运行 Recall@{topK}</button></div>
      <form className="evaluation-form" onSubmit={addEvaluationCase}>
        <label className="sr-only" htmlFor="evaluation-query">标准评测问题</label>
        <input id="evaluation-query" onChange={(event) => setEvaluationQuery(event.target.value)} placeholder="输入一个标准问题" required value={evaluationQuery} />
        <label className="sr-only" htmlFor="evaluation-document">期望命中的文档</label>
        <select id="evaluation-document" onChange={(event) => setEvaluationDocumentId(event.target.value)} required value={evaluationDocumentId}><option value="">选择期望命中的文档</option>{documents.filter((doc) => doc.enabled).map((doc) => <option key={doc.id} value={doc.id}>{doc.title}</option>)}</select>
        <button className="secondary-button" type="submit">加入评测集</button>
      </form>
      <div className="evaluation-summary"><span>用例 <b>{evaluationCases.length}</b></span>{evaluationReport && <><span>Recall@{evaluationReport.top_k} <b>{(evaluationReport.recall_at_k * 100).toFixed(1)}%</b></span><span>MRR <b>{evaluationReport.mean_reciprocal_rank.toFixed(3)}</b></span><span>命中率 <b>{(evaluationReport.hit_rate * 100).toFixed(1)}%</b></span></>}</div>
    </article>
  </div>
}

export function TasksPage() {
  const { visibleTasks, tasks, resolvedFailureCount, showResolvedFailures, setShowResolvedFailures, taskAction, workspaceLoading } = useWorkspace()
  return <article className="panel data-panel">
    <div className="section-title"><div><span className="panel-kicker">BACKGROUND JOBS</span><h2>任务队列</h2></div><div className="section-actions"><span>{visibleTasks.length} / {tasks.length} 项</span>{resolvedFailureCount > 0 && <button onClick={() => setShowResolvedFailures((value) => !value)} type="button">{showResolvedFailures ? '隐藏' : '显示'} {resolvedFailureCount} 条早期失败</button>}</div></div>
    {workspaceLoading ? <p className="panel-empty">正在读取后台任务…</p> : visibleTasks.length ? <div className="task-list">{visibleTasks.map((task) => {
      const resolved = isResolvedHistoricalFailure(task, tasks)
      const running = !terminalTaskStates.has(task.status)
      const retryable = ['failed', 'cancelled', 'partially_completed'].includes(task.status)
      return <article className={resolved ? 'resolved-task' : ''} key={task.id}><div className="task-head"><b>{resolved ? '早期失败' : taskLabels[task.status] ?? task.status}{resolved && <em>后续已成功</em>}</b><span>{task.progress}%</span></div><div className="progress-track"><i style={{ width: `${task.progress}%` }} /></div><p>{task.current_stage ?? task.payload.seed_url ?? task.payload.file_name}</p>{task.retry_of_task_id && <p className="task-resolution">这是失败任务的重试，原任务 {task.retry_of_task_id.slice(0, 8)}。</p>}{resolved && <p className="task-resolution">相同入口的后续任务已经完成；保留本记录用于复盘。</p>}{task.error_message && <small>{task.error_message}</small>}<div className="task-actions">{running && task.status !== 'paused' && <button onClick={() => taskAction(task.id, 'pause')} type="button">暂停</button>}{task.status === 'paused' && <button onClick={() => taskAction(task.id, 'resume')} type="button">继续</button>}{running && <button className="danger-text" onClick={() => taskAction(task.id, 'cancel')} type="button">取消</button>}{retryable && <button onClick={() => taskAction(task.id, 'retry')} type="button">重试</button>}</div></article>
    })}</div> : <p className="panel-empty">还没有后台任务。</p>}
  </article>
}

export function ExportPage() {
  const { activeId, busy, downloadExport, createSnapshot, consistency, checkConsistency, repairConsistency } = useWorkspace()
  return <div className="export-layout">
    <article className="panel export-card"><span className="panel-kicker">PORTABLE KNOWLEDGE BASE</span><h2>可移植知识库</h2><p>流式生成 Markdown、Chunk JSONL、来源清单、Manifest 与重建检索示例，适合交付给其他用户或换数据库。</p><div><span>documents/</span><span>chunks.jsonl</span><span>manifest.json</span><span>examples/rebuild_and_search.py</span></div><div className="card-actions"><button className="secondary-button" disabled={!activeId || busy === 'export'} onClick={downloadExport} type="button">下载 .zip</button><button className="secondary-button" disabled={!activeId || busy === 'snapshot'} onClick={createSnapshot} type="button">创建 Qdrant 快照</button></div></article>
    <article className="panel consistency-card"><span className="panel-kicker">INDEX INTEGRITY</span><h2>索引一致性</h2><p>对比 PostgreSQL 中的 Chunk 与 Qdrant Point ID，并验证当前模型签名，发现中断写入留下的缺失或孤儿向量。</p>{consistency ? <div className={`consistency-result ${consistency.consistent ? 'ok' : 'bad'}`}><strong>{consistency.consistent ? '✓ 数据一致' : '! 需要修复'}</strong><span>PostgreSQL {consistency.postgres_chunk_count} · Qdrant {consistency.qdrant_point_count}</span><small>缺失 {consistency.missing_point_ids.length} · 孤儿 {consistency.orphan_point_ids.length} · 模型签名 {consistency.model_signature_matches ? '匹配' : '不匹配'}</small></div> : <p className="panel-empty">尚未运行一致性检查。</p>}<div className="card-actions"><button className="secondary-button" disabled={!activeId || busy === 'consistency'} onClick={checkConsistency} type="button">检查一致性</button><button className="primary-button" disabled={!activeId || busy === 'repair'} onClick={repairConsistency} type="button">安全重建修复</button></div></article>
  </div>
}
