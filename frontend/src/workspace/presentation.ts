import type { IngestionTask, SearchHit } from '../api'

export const terminalTaskStates = new Set(['completed', 'failed', 'cancelled', 'partially_completed'])

export const taskLabels: Record<string, string> = {
  pending: '等待中', crawling: '抓取网页', parsing: '解析正文', chunking: '文本切片',
  embedding: '生成向量', indexing: '写入 Qdrant', completed: '已完成', failed: '失败',
  retrying: '正在恢复', paused: '已暂停', cancelled: '已取消', partially_completed: '部分完成',
}

export function formatTime(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '—'
}

export function formatPrimaryScore(hit: SearchHit) {
  return hit.match_type === 'keyword' ? hit.score.toFixed(3) : `${(hit.score * 100).toFixed(1)}%`
}

export function formatComponentScore(value: number | null, percentage: boolean) {
  if (value == null) return '—'
  return percentage ? `${(value * 100).toFixed(1)}%` : value.toFixed(3)
}

export function deriveCrawlScope(value: string) {
  try {
    const parsed = new URL(value)
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('unsupported protocol')
    const lastSlash = parsed.pathname.lastIndexOf('/')
    return { host: parsed.hostname, prefix: parsed.pathname.slice(0, lastSlash + 1) || '/' }
  } catch {
    return { host: '等待有效网址', prefix: '自动识别' }
  }
}

export function isResolvedHistoricalFailure(task: IngestionTask, allTasks: IngestionTask[]) {
  if (task.status !== 'failed' || !task.payload.seed_url) return false
  return allTasks.some((candidate) => (
    candidate.status === 'completed'
    && candidate.payload.seed_url === task.payload.seed_url
    && new Date(candidate.created_at).getTime() > new Date(task.created_at).getTime()
  ))
}
