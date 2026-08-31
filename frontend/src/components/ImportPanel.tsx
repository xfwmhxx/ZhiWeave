import { useWorkspace } from '../workspace/context'

export function ImportPanel() {
  const {
    importMode, setImportMode, startImport, uploadDocument, seedUrl, setSeedUrl,
    maxPages, setMaxPages, crawlScope, uploadFile, setUploadFile, busy,
  } = useWorkspace()

  return <article className="panel import-panel">
    <div className="panel-heading">
      <div>
        <span className="panel-kicker">01 · ADD SOURCE</span>
        <h2>添加学习资料</h2>
        <p>{importMode === 'web' ? '系统会自动识别域名和父目录，抓取同域、同目录页面并保留来源地址。' : '本地解析 Markdown、TXT 或 PDF；文件不会交给外部模型服务。'}</p>
      </div>
      <span className="source-type">{importMode === 'web' ? 'URL' : 'FILE'}</span>
    </div>
    <div className="segmented import-tabs">
      <button className={importMode === 'web' ? 'active' : ''} onClick={() => setImportMode('web')} type="button">网页抓取</button>
      <button className={importMode === 'file' ? 'active' : ''} onClick={() => setImportMode('file')} type="button">上传文件</button>
    </div>
    {importMode === 'web' ? <form className="import-form" onSubmit={startImport}>
      <label htmlFor="seed-url">网页或教程入口网址</label>
      <div className="url-field">
        <span aria-hidden="true">↗</span>
        <input id="seed-url" onChange={(event) => setSeedUrl(event.target.value)} value={seedUrl} />
        <button className="primary-button" disabled={busy === 'import'} type="submit">{busy === 'import' ? '提交中…' : '开始构建'}</button>
      </div>
      <div className="form-options">
        <label>最多抓取 <input type="number" min="1" max="100" value={maxPages} onChange={(event) => setMaxPages(Number(event.target.value))} /> 页</label>
        <span>请求间隔 <b>0.6s</b></span><span>目标域名 <b>{crawlScope.host}</b></span><span>目录范围 <b>{crawlScope.prefix}</b></span>
      </div>
    </form> : <form className="import-form upload-form" onSubmit={uploadDocument}>
      <label htmlFor="source-file">选择学习文档</label>
      <div className="file-drop">
        <input accept=".md,.markdown,.txt,.pdf" id="source-file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} type="file" />
        <div><strong>{uploadFile?.name ?? 'Markdown、TXT 或 PDF'}</strong><span>{uploadFile ? `${(uploadFile.size / 1024).toFixed(1)} KB` : '单文件最大 20 MB'}</span></div>
        <button className="primary-button" disabled={!uploadFile || busy === 'upload'} type="submit">{busy === 'upload' ? '提交中…' : '上传并构建'}</button>
      </div>
    </form>}
  </article>
}
