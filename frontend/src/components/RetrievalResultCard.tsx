import { useMemo, useState } from 'react'

import { api, type Chunk, type ChunkContext, type SearchHit } from '../api'
import { formatComponentScore, formatPrimaryScore } from '../workspace/presentation'

type Props = {
  activeId: string
  hit: SearchHit
  index: number
  query: string
}

function queryTerms(query: string) {
  const terms = new Set(query.match(/[a-z0-9_+#.-]{2,}/gi) ?? [])
  for (const run of query.match(/[\u3400-\u9fff]{2,}/g) ?? []) {
    if (run.length <= 4) terms.add(run)
    else for (let index = 0; index < run.length - 1; index += 1) terms.add(run.slice(index, index + 2))
  }
  return [...terms].sort((left, right) => right.length - left.length)
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  const highlight = useMemo(() => {
    const terms = queryTerms(query)
    const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    return {
      matcher: escaped.length ? new RegExp(`(${escaped.join('|')})`, 'gi') : null,
      terms: new Set(terms.map((term) => term.toLowerCase())),
    }
  }, [query])
  if (!highlight.matcher) return text
  return text.split(highlight.matcher).map((part, index) => (
    highlight.terms.has(part.toLowerCase()) ? <mark key={`${part}-${index}`}>{part}</mark> : part
  ))
}

function Neighbor({ chunk, label }: { chunk: Chunk | null; label: string }) {
  if (!chunk) return <div className="context-neighbor context-missing"><b>{label}</b><span>没有更多内容</span></div>
  return <div className="context-neighbor"><b>{label} · Chunk #{chunk.sequence_index + 1}</b><pre>{chunk.content}</pre></div>
}

export function RetrievalResultCard({ activeId, hit, index, query }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [context, setContext] = useState<ChunkContext | null>(null)
  const [contextLoading, setContextLoading] = useState(false)
  const [contextError, setContextError] = useState('')

  async function toggleContext() {
    if (context) { setContext(null); return }
    setContextLoading(true); setContextError('')
    try {
      setContext(await api<ChunkContext>(`/knowledge-bases/${activeId}/chunks/${hit.chunk_id}/context`))
    } catch (reason) {
      setContextError((reason as Error).message)
    } finally {
      setContextLoading(false)
    }
  }

  return <article className="panel result-card">
    <header><span>TOP {index + 1} · {hit.match_type}</span><b>{formatPrimaryScore(hit)}</b></header>
    <div className="score-details"><span>Cosine {formatComponentScore(hit.semantic_score, true)}</span><span>BM25 {formatComponentScore(hit.keyword_score, false)}</span>{hit.reranker_score != null && <span>Reranker {formatComponentScore(hit.reranker_score, false)}</span>}</div>
    <h3>{hit.title}</h3>
    <div className="result-breadcrumb"><span>{hit.section_heading ?? '未识别章节'}</span><span>Chunk #{hit.sequence_index + 1}</span><span>{hit.character_count} 字符</span></div>
    <pre className={expanded ? 'result-content expanded' : 'result-content'}><HighlightedText text={hit.content} query={query} /></pre>
    <div className="result-actions">
      <button onClick={() => setExpanded((value) => !value)} type="button">{expanded ? '收起 Chunk' : '展开完整 Chunk'}</button>
      <button disabled={contextLoading} onClick={toggleContext} type="button">{contextLoading ? '读取中…' : context ? '收起前后文' : '查看前后文'}</button>
      {hit.source_uri && <a href={hit.source_uri} target="_blank" rel="noreferrer">查看原始页面 ↗</a>}
    </div>
    {contextError && <p className="context-error">{contextError}</p>}
    {context && <div className="chunk-context"><Neighbor chunk={context.previous_chunk} label="上一段" /><Neighbor chunk={context.next_chunk} label="下一段" /></div>}
  </article>
}
