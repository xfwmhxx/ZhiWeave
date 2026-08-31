export const navigation = [
  { id: 'overview', label: '知识库总览', glyph: '⌂', path: '/' },
  { id: 'sources', label: '数据源', glyph: '↗', path: '/sources' },
  { id: 'chunks', label: 'Chunk 工作台', glyph: '▤', path: '/chunks' },
  { id: 'retrieval', label: '检索实验室', glyph: '⌕', path: '/retrieval' },
  { id: 'tasks', label: '任务队列', glyph: '◷', path: '/tasks' },
  { id: 'export', label: '导出', glyph: '⇩', path: '/export' },
  { id: 'guide', label: '使用指南', glyph: '?', path: '/guide' },
] as const

export type NavigationId = (typeof navigation)[number]['id']

export const guideSections = [
  { id: 'guide-start', number: '01', label: '快速开始', description: '认识完整流程' },
  { id: 'guide-import', number: '02', label: '导入资料', description: '网页与本地文件' },
  { id: 'guide-inspect', number: '03', label: '检查数据', description: '核对来源与 Chunk' },
  { id: 'guide-retrieve', number: '04', label: '检索评测', description: '向量、BM25 与混合' },
  { id: 'guide-export', number: '05', label: '运维与导出', description: '任务、一致性与迁移' },
  { id: 'guide-faq', number: '06', label: '常见问题', description: '第一次使用必读' },
] as const
