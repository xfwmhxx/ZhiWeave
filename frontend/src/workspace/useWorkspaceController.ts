import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'

import {
  api,
  apiDownload,
  apiForm,
  configureApiKey,
  type Chunk,
  type ConsistencyReport,
  type Document,
  type EvaluationCase,
  type EvaluationReport,
  type HealthReport,
  type IngestionTask,
  type KnowledgeBase,
  type SearchHit,
} from '../api'
import { navigation, type NavigationId } from './navigation'
import { deriveCrawlScope, isResolvedHistoricalFailure, terminalTaskStates } from './presentation'

type WorkspaceData = {
  documents: Document[]
  tasks: IngestionTask[]
  chunks: Chunk[]
  evaluationCases: EvaluationCase[]
}

export function useWorkspaceController() {
  const routerNavigate = useNavigate()
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [activeId, setActiveId] = useState('')
  const [documents, setDocuments] = useState<Document[]>([])
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [tasks, setTasks] = useState<IngestionTask[]>([])
  const [evaluationCases, setEvaluationCases] = useState<EvaluationCase[]>([])
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null)
  const [consistency, setConsistency] = useState<ConsistencyReport | null>(null)
  const [health, setHealth] = useState<HealthReport | null>(null)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [seedUrl, setSeedUrl] = useState('https://www.runoob.com/mysql/mysql-tutorial.html')
  const [maxPages, setMaxPages] = useState(40)
  const [importMode, setImportMode] = useState<'web' | 'file'>('web')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [query, setQuery] = useState('请概括这套资料的核心知识点')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [searchMode, setSearchMode] = useState<'semantic' | 'keyword' | 'hybrid'>('hybrid')
  const [topK, setTopK] = useState(5)
  const [scoreThreshold, setScoreThreshold] = useState('')
  const [languageFilter, setLanguageFilter] = useState('')
  const [sourceTypeFilter, setSourceTypeFilter] = useState('')
  const [useReranker, setUseReranker] = useState(false)
  const [expandQuery, setExpandQuery] = useState(true)
  const [evaluationQuery, setEvaluationQuery] = useState('')
  const [evaluationDocumentId, setEvaluationDocumentId] = useState('')
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showResolvedFailures, setShowResolvedFailures] = useState(false)
  const [newName, setNewName] = useState('网页学习知识库')

  const activeKb = useMemo(
    () => knowledgeBases.find((item) => item.id === activeId) ?? null,
    [activeId, knowledgeBases],
  )
  const crawlScope = useMemo(() => deriveCrawlScope(seedUrl), [seedUrl])
  const latestTask = tasks[0] ?? null
  const activeTask = tasks.find((task) => !terminalTaskStates.has(task.status)) ?? null
  const resolvedFailureCount = useMemo(
    () => tasks.filter((task) => isResolvedHistoricalFailure(task, tasks)).length,
    [tasks],
  )
  const visibleTasks = useMemo(
    () => showResolvedFailures ? tasks : tasks.filter((task) => !isResolvedHistoricalFailure(task, tasks)),
    [showResolvedFailures, tasks],
  )

  const fetchWorkspace = useCallback(async (knowledgeBaseId: string): Promise<WorkspaceData> => {
    const [workspaceDocuments, workspaceTasks, workspaceChunks, workspaceCases] = await Promise.all([
      api<Document[]>(`/knowledge-bases/${knowledgeBaseId}/documents`),
      api<IngestionTask[]>(`/knowledge-bases/${knowledgeBaseId}/tasks`),
      api<Chunk[]>(`/knowledge-bases/${knowledgeBaseId}/chunks?limit=100`),
      api<EvaluationCase[]>(`/knowledge-bases/${knowledgeBaseId}/evaluation-cases`),
    ])
    return {
      documents: workspaceDocuments,
      tasks: workspaceTasks,
      chunks: workspaceChunks,
      evaluationCases: workspaceCases,
    }
  }, [])

  const applyWorkspace = useCallback((data: WorkspaceData) => {
    setDocuments(data.documents)
    setTasks(data.tasks)
    setChunks(data.chunks)
    setEvaluationCases(data.evaluationCases)
  }, [])

  const loadWorkspace = useCallback(async (knowledgeBaseId: string) => {
    if (!knowledgeBaseId) return
    applyWorkspace(await fetchWorkspace(knowledgeBaseId))
  }, [applyWorkspace, fetchWorkspace])

  const selectKnowledgeBase = useCallback((knowledgeBaseId: string) => {
    if (knowledgeBaseId === activeId) return
    setHits([])
    setConsistency(null)
    setEvaluationReport(null)
    setDocuments([])
    setTasks([])
    setChunks([])
    setEvaluationCases([])
    setWorkspaceLoading(Boolean(knowledgeBaseId))
    setActiveId(knowledgeBaseId)
  }, [activeId])

  const loadKnowledgeBases = useCallback(async () => {
    const data = await api<KnowledgeBase[]>('/knowledge-bases')
    setKnowledgeBases(data)
    const nextId = data.some((item) => item.id === activeId) ? activeId : data[0]?.id || ''
    if (nextId !== activeId) selectKnowledgeBase(nextId)
  }, [activeId, selectKnowledgeBase])

  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      try {
        const [report, bases] = await Promise.all([
          api<HealthReport>('/health/ready'), api<KnowledgeBase[]>('/knowledge-bases'),
        ])
        if (cancelled) return
        setHealth(report)
        setKnowledgeBases(bases)
        const firstKnowledgeBaseId = bases[0]?.id ?? ''
        setWorkspaceLoading(Boolean(firstKnowledgeBaseId))
        setActiveId(firstKnowledgeBaseId)
      } catch (reason) {
        if (!cancelled) setError(`后端暂未连接：${(reason as Error).message}`)
      }
    }
    void bootstrap()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    void fetchWorkspace(activeId)
      .then((data) => { if (!cancelled) applyWorkspace(data) })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message) })
      .finally(() => { if (!cancelled) setWorkspaceLoading(false) })
    return () => { cancelled = true }
  }, [activeId, applyWorkspace, fetchWorkspace])

  useEffect(() => {
    if (!activeId || !activeTask) return
    const timer = window.setInterval(() => {
      Promise.all([loadWorkspace(activeId), loadKnowledgeBases()]).catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [activeId, activeTask, loadKnowledgeBases, loadWorkspace])

  function navigateTo(target: NavigationId) {
    const destination = navigation.find((item) => item.id === target)?.path ?? '/'
    routerNavigate(destination)
    setShowProfile(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function createKnowledgeBase(event: FormEvent) {
    event.preventDefault(); setBusy('create'); setError('')
    try {
      const created = await api<KnowledgeBase>('/knowledge-bases', {
        method: 'POST',
        body: JSON.stringify({ name: newName, description: '从公开网页或本地文档构建，用于学习与验证 RAG 检索链路。' }),
      })
      await loadKnowledgeBases(); selectKnowledgeBase(created.id); setShowCreate(false)
      setMessage('知识库已经创建，可以开始导入学习资料。')
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function startImport(event: FormEvent) {
    event.preventDefault()
    if (!activeId) { setShowCreate(true); return }
    setBusy('import'); setError(''); setMessage('')
    try {
      await api<IngestionTask>(`/knowledge-bases/${activeId}/imports/web`, {
        method: 'POST', body: JSON.stringify({ seed_url: seedUrl, max_pages: maxPages }),
      })
      setMessage('抓取任务已进入 Celery 队列。页面会自动刷新进度。')
      await Promise.all([loadWorkspace(activeId), loadKnowledgeBases()])
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function uploadDocument(event: FormEvent) {
    event.preventDefault()
    if (!activeId || !uploadFile) return
    setBusy('upload'); setError(''); setMessage('')
    const form = new FormData(); form.append('file', uploadFile)
    try {
      await apiForm<IngestionTask>(`/knowledge-bases/${activeId}/imports/files`, form)
      setMessage(`${uploadFile.name} 已进入解析与向量化队列。`)
      setUploadFile(null)
      await Promise.all([loadWorkspace(activeId), loadKnowledgeBases()])
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function runSearch(event: FormEvent) {
    event.preventDefault(); if (!activeId) return
    setBusy('search'); setError('')
    try {
      setHits(await api<SearchHit[]>(`/knowledge-bases/${activeId}/search`, {
        method: 'POST', body: JSON.stringify({
          query, top_k: topK, mode: searchMode,
          score_threshold: scoreThreshold ? Number(scoreThreshold) : null,
          language: languageFilter || null,
          source_type: sourceTypeFilter || null,
          use_reranker: useReranker,
          expand_query: expandQuery,
        }),
      }))
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function documentAction(documentId: string, action: 'refetch' | 'reindex' | 'delete') {
    if (!activeId) return
    if (action === 'delete' && !window.confirm('确定删除这份文档及其全部 Chunk 和向量吗？')) return
    setBusy(`${action}:${documentId}`); setError('')
    try {
      const suffix = action === 'delete' ? '' : `/${action}`
      await api<IngestionTask>(`/knowledge-bases/${activeId}/documents/${documentId}${suffix}`, { method: action === 'delete' ? 'DELETE' : 'POST' })
      setMessage(action === 'delete' ? '文档删除任务已提交。' : '文档更新任务已提交。')
      await loadWorkspace(activeId)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function toggleDocument(documentId: string, enabled: boolean) {
    if (!activeId) return
    setBusy(`toggle:${documentId}`); setError('')
    try {
      await api<unknown>(`/knowledge-bases/${activeId}/documents/${documentId}/${enabled ? 'disable' : 'enable'}`, { method: 'POST' })
      setMessage(enabled ? '文档已停用，并从当前向量索引移除。' : '文档已启用，重建任务已经进入队列。')
      await loadWorkspace(activeId)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function taskAction(taskId: string, action: 'cancel' | 'pause' | 'resume' | 'retry') {
    if (!activeId) return
    setBusy(`${action}:${taskId}`); setError('')
    try {
      await api<IngestionTask>(`/knowledge-bases/${activeId}/tasks/${taskId}/${action}`, { method: 'POST' })
      setMessage(`任务操作“${action}”已提交。`)
      await loadWorkspace(activeId)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function addEvaluationCase(event: FormEvent) {
    event.preventDefault(); if (!activeId || !evaluationDocumentId) return
    setBusy('evaluation-case'); setError('')
    try {
      await api<EvaluationCase>(`/knowledge-bases/${activeId}/evaluation-cases`, {
        method: 'POST',
        body: JSON.stringify({ query: evaluationQuery, relevant_document_id: evaluationDocumentId }),
      })
      setEvaluationQuery(''); setEvaluationDocumentId(''); await loadWorkspace(activeId)
      setMessage('评测问题已加入数据集。')
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function runEvaluation() {
    if (!activeId) return
    setBusy('evaluation-run'); setError('')
    try {
      setEvaluationReport(await api<EvaluationReport>(`/knowledge-bases/${activeId}/evaluation-runs`, {
        method: 'POST', body: JSON.stringify({ top_k: topK, mode: searchMode }),
      }))
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function checkConsistency() {
    if (!activeId) return
    setBusy('consistency'); setError('')
    try { setConsistency(await api<ConsistencyReport>(`/knowledge-bases/${activeId}/consistency`)) }
    catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function repairConsistency() {
    if (!activeId) return
    setBusy('repair'); setError('')
    try {
      await api<IngestionTask>(`/knowledge-bases/${activeId}/consistency/repair`, { method: 'POST' })
      setMessage('一致性修复已进入安全重建队列。'); await loadWorkspace(activeId)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function saveKnowledgeBaseSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeId) return
    const form = new FormData(event.currentTarget)
    setBusy('settings-save'); setError('')
    try {
      await api<KnowledgeBase>(`/knowledge-bases/${activeId}`, { method: 'PATCH', body: JSON.stringify({
        name: form.get('name'), description: form.get('description') || null,
        retrieval_mode: form.get('retrieval_mode'), semantic_weight: Number(form.get('semantic_weight')),
        keyword_weight: Number(form.get('keyword_weight')),
        score_threshold: form.get('score_threshold') ? Number(form.get('score_threshold')) : null,
      }) })
      await loadKnowledgeBases(); setMessage('知识库与检索配置已保存。'); setShowSettings(false)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function startKnowledgeBaseReindex(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeId) return
    const form = new FormData(event.currentTarget)
    if (!window.confirm('整库重建会生成新索引，全部成功后再切换。确定开始吗？')) return
    setBusy('kb-reindex'); setError('')
    try {
      await api<IngestionTask>(`/knowledge-bases/${activeId}/reindex`, { method: 'POST', body: JSON.stringify({
        embedding_model: form.get('embedding_model'), embedding_revision: form.get('embedding_revision'),
        embedding_dimension: Number(form.get('embedding_dimension')),
        chunk_size: Number(form.get('chunk_size')), chunk_overlap: Number(form.get('chunk_overlap')),
        chunk_strategy: form.get('chunk_strategy'),
      }) })
      setShowSettings(false); setMessage('整库重建已进入队列，旧索引会继续服务到新索引完整可用。'); await loadWorkspace(activeId)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function deleteKnowledgeBase() {
    if (!activeId || !activeKb || !window.confirm(`确定删除知识库“${activeKb.name}”吗？文档、任务和 Qdrant Collection 都会删除。`)) return
    setBusy('kb-delete'); setError('')
    try {
      await api<IngestionTask>(`/knowledge-bases/${activeId}`, { method: 'DELETE' })
      setShowSettings(false); selectKnowledgeBase(''); setMessage('知识库删除任务已提交。'); await loadKnowledgeBases()
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  async function createSnapshot() {
    if (!activeId) return
    setBusy('snapshot'); setError('')
    try {
      await api(`/knowledge-bases/${activeId}/snapshots`, { method: 'POST' })
      setMessage('Qdrant 快照已创建。')
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  function configureAccess() {
    const value = window.prompt('输入 API Key；本地未启用鉴权时留空即可。', window.localStorage.getItem('zhiweave_api_key') ?? '')
    if (value == null) return
    configureApiKey(value); window.location.reload()
  }

  async function downloadExport() {
    if (!activeId) return
    setBusy('export'); setError('')
    try {
      const blob = await apiDownload(`/knowledge-bases/${activeId}/export`)
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a')
      anchor.href = url; anchor.download = `zhiweave-${activeId}.zip`; anchor.click()
      URL.revokeObjectURL(url)
    } catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }

  function dismissNotice() { setError(''); setMessage('') }

  return {
    knowledgeBases, activeId, activeKb, documents, chunks, tasks, evaluationCases,
    evaluationReport, consistency, health, workspaceLoading, seedUrl, maxPages, importMode,
    uploadFile, query, hits, searchMode, topK, scoreThreshold, languageFilter,
    sourceTypeFilter, useReranker, expandQuery, evaluationQuery, evaluationDocumentId,
    busy, message, error, showCreate, showSettings, showProfile, showResolvedFailures,
    newName, crawlScope, latestTask, activeTask, resolvedFailureCount, visibleTasks,
    setSeedUrl, setMaxPages, setImportMode, setUploadFile, setQuery, setSearchMode,
    setTopK, setScoreThreshold, setLanguageFilter, setSourceTypeFilter, setUseReranker,
    setExpandQuery, setEvaluationQuery, setEvaluationDocumentId, setShowCreate,
    setShowSettings, setShowProfile, setShowResolvedFailures, setNewName,
    navigateTo, selectKnowledgeBase, createKnowledgeBase, startImport, uploadDocument,
    runSearch, documentAction, toggleDocument, taskAction, addEvaluationCase,
    runEvaluation, checkConsistency, repairConsistency, saveKnowledgeBaseSettings,
    startKnowledgeBaseReindex, deleteKnowledgeBase, createSnapshot, configureAccess,
    downloadExport, dismissNotice,
  }
}

export type WorkspaceController = ReturnType<typeof useWorkspaceController>
