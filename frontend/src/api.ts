export type KnowledgeBase = {
  id: string
  workspace_id: string
  name: string
  description: string | null
  status: 'active' | 'archived' | 'deleting' | 'failed'
  embedding_model: string
  embedding_revision: string
  embedding_dimension: number
  embedding_query_prefix: string
  embedding_passage_prefix: string
  embedding_signature: string
  chunk_size: number
  chunk_overlap: number
  chunk_strategy: 'character' | 'token'
  vector_collection_name: string
  index_version: number
  retrieval_mode: 'semantic' | 'keyword' | 'hybrid'
  semantic_weight: number
  keyword_weight: number
  score_threshold: number | null
  reranker_model: string | null
  last_consistency_check_at: string | null
  last_consistency_report: ConsistencyReport | Record<string, never>
  document_count: number
  chunk_count: number
  active_task_count: number
  created_at: string
  updated_at: string
}

export type Document = {
  id: string
  source_type: 'markdown' | 'web_page' | 'pdf' | 'plain_text'
  status: 'pending' | 'processing' | 'ready' | 'failed' | 'deleting'
  title: string
  file_name: string | null
  mime_type: string | null
  source_uri: string | null
  canonical_uri: string | null
  language: string | null
  content_hash: string | null
  fetched_at: string | null
  indexed_at: string | null
  version: number
  enabled: boolean
  vector_sync_status: 'pending' | 'synced' | 'error'
  vector_sync_error: string | null
  extra_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type Chunk = {
  id: string
  document_id: string
  sequence_index: number
  content: string
  content_hash: string
  character_count: number
  start_offset: number | null
  end_offset: number | null
  extra_metadata: { title?: string; source_uri?: string }
}

export type IngestionTask = {
  id: string
  task_type: string
  status: string
  progress: number
  current_stage: string | null
  error_message: string | null
  cancel_requested: boolean
  pause_requested: boolean
  retry_of_task_id: string | null
  payload: { seed_url?: string; max_pages?: number; file_name?: string; kind?: string }
  result: Record<string, unknown>
  created_at: string
  finished_at: string | null
}

export type SearchHit = {
  score: number
  semantic_score: number | null
  keyword_score: number | null
  reranker_score: number | null
  match_type: 'semantic' | 'keyword' | 'hybrid'
  chunk_id: string
  document_id: string
  sequence_index: number
  content: string
  title: string
  source_uri: string | null
}

export type ConsistencyReport = {
  consistent: boolean
  postgres_chunk_count: number
  qdrant_point_count: number
  missing_point_ids: string[]
  orphan_point_ids: string[]
  model_signature_matches: boolean
  checked_at: string
}

export type EvaluationCase = {
  id: string
  query: string
  relevant_document_id: string | null
  relevant_chunk_id: string | null
  notes: string | null
  created_at: string
}

export type EvaluationReport = {
  mode: 'semantic' | 'keyword' | 'hybrid'
  top_k: number
  case_count: number
  hit_rate: number
  recall_at_k: number
  mean_reciprocal_rank: number
  results: Array<{ case_id: string; query: string; hit: boolean; rank: number | null }>
}

export type HealthReport = {
  status: 'ready' | 'not_ready'
  checks?: Record<string, { status: 'up' | 'down'; latency_ms: number }>
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function accessHeaders(): Record<string, string> {
  const key = window.localStorage.getItem('zhiweave_api_key')
  return key ? { 'X-API-Key': key } : {}
}

export function configureApiKey(value: string) {
  if (value.trim()) window.localStorage.setItem('zhiweave_api_key', value.trim())
  else window.localStorage.removeItem('zhiweave_api_key')
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...accessHeaders(), ...init?.headers },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(body?.detail ?? `请求失败（${response.status}）`, response.status)
  }
  return (await response.json()) as T
}

export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: 'POST', body: form, headers: accessHeaders(),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(body?.detail ?? `请求失败（${response.status}）`, response.status)
  }
  return (await response.json()) as T
}

export async function apiDownload(path: string): Promise<Blob> {
  const response = await fetch(`/api/v1${path}`, { headers: accessHeaders() })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new ApiError(body?.detail ?? `下载失败（${response.status}）`, response.status)
  }
  return response.blob()
}
