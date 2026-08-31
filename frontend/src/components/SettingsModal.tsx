import { useWorkspace } from '../workspace/context'

export function SettingsModal() {
  const {
    showSettings, setShowSettings, activeKb, saveKnowledgeBaseSettings,
    startKnowledgeBaseReindex, deleteKnowledgeBase, busy, navigateTo,
  } = useWorkspace()
  if (!showSettings) return null

  return <div className="modal-backdrop" onMouseDown={() => setShowSettings(false)}>
    <section className="modal settings-modal editable-settings" key={activeKb?.id} role="dialog" aria-modal="true" aria-labelledby="settings-title" onMouseDown={(event) => event.stopPropagation()}>
      <span className="panel-kicker">KNOWLEDGE BASE SETTINGS</span><h2 id="settings-title">知识库与索引配置</h2>
      {activeKb ? <div className="settings-scroll">
        <form className="settings-form" onSubmit={saveKnowledgeBaseSettings}>
          <h3>基本信息与检索策略</h3>
          <label>名称<input defaultValue={activeKb.name} name="name" required /></label>
          <label>说明<textarea defaultValue={activeKb.description ?? ''} name="description" /></label>
          <div className="settings-field-grid">
            <label>默认检索<select defaultValue={activeKb.retrieval_mode} name="retrieval_mode"><option value="hybrid">混合 RRF</option><option value="semantic">纯向量</option><option value="keyword">关键词 BM25</option></select></label>
            <label>向量权重<input defaultValue={activeKb.semantic_weight} max="1" min="0" name="semantic_weight" step="0.1" type="number" /></label>
            <label>关键词权重<input defaultValue={activeKb.keyword_weight} max="1" min="0" name="keyword_weight" step="0.1" type="number" /></label>
            <label>最低相似度<input defaultValue={activeKb.score_threshold ?? ''} max="1" min="0" name="score_threshold" placeholder="不限制" step="0.05" type="number" /></label>
          </div>
          <button className="primary-button" disabled={busy === 'settings-save'} type="submit">保存设置</button>
        </form>
        <form className="settings-form reindex-form" onSubmit={startKnowledgeBaseReindex}>
          <h3>向量空间与切片</h3>
          <p>这些参数不能直接覆盖现有向量。系统会构建新 Collection，完成后原子切换；旧 Collection 清理失败只会记录警告，不会回删已经启用的新索引。</p>
          <div className="settings-field-grid">
            <label>Embedding 模型<input defaultValue={activeKb.embedding_model} name="embedding_model" /></label>
            <label>模型 revision<input defaultValue={activeKb.embedding_revision} name="embedding_revision" /></label>
            <label>向量维度<input defaultValue={activeKb.embedding_dimension} min="1" name="embedding_dimension" type="number" /></label>
            <label>切片计量<select defaultValue={activeKb.chunk_strategy} name="chunk_strategy"><option value="character">字符</option><option value="token">模型 Token</option></select></label>
            <label>Chunk 大小<input defaultValue={activeKb.chunk_size} min="100" name="chunk_size" type="number" /></label>
            <label>Chunk 重叠<input defaultValue={activeKb.chunk_overlap} min="0" name="chunk_overlap" type="number" /></label>
            <span className="signature-field">索引版本<b>v{activeKb.index_version}</b><small>{activeKb.embedding_signature.slice(0, 16)}…</small></span>
          </div>
          <button className="secondary-button" disabled={busy === 'kb-reindex'} type="submit">安全重建整个知识库</button>
        </form>
        <div className="danger-zone"><div><strong>删除知识库</strong><p>通过后台任务删除 PostgreSQL 数据、Qdrant Collection 和对应上传临时目录。</p></div><button className="danger-button" disabled={busy === 'kb-delete'} onClick={deleteKnowledgeBase} type="button">删除知识库</button></div>
      </div> : <p>请先选择一个知识库。</p>}
      <div className="modal-footer"><button className="secondary-button" onClick={() => setShowSettings(false)} type="button">关闭</button><button className="secondary-button" onClick={() => { setShowSettings(false); navigateTo('guide') }} type="button">查看使用指南</button></div>
    </section>
  </div>
}
