import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { useWorkspace } from '../workspace/context'
import { guideSections } from '../workspace/navigation'

export function GuidePage() {
  const { navigateTo } = useWorkspace()
  const [activeSection, setActiveSection] = useState('guide-start')

  useEffect(() => {
    const sections = guideSections
      .map((item) => document.getElementById(item.id))
      .filter((section): section is HTMLElement => Boolean(section))
    const observer = new IntersectionObserver((entries) => {
      const visibleSection = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0]
      if (visibleSection) setActiveSection(visibleSection.target.id)
    }, { rootMargin: '-80px 0px -58% 0px', threshold: [0, 0.1, 0.25] })
    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [])

  return <div className="guide-page">
    <aside className="guide-sidebar">
      <Link className="guide-brand" to="/" aria-label="返回 ZhiWeave 知识库总览"><img src="/zhiweave-logo-v1.png" alt="" /><span><strong>ZhiWeave</strong><small>织知 · Guide</small></span></Link>
      <select className="guide-mobile-nav" value={activeSection} onChange={(event) => { setActiveSection(event.target.value); window.location.hash = event.target.value }} aria-label="移动端指南目录">{guideSections.map((item) => <option key={item.id} value={item.id}>{item.number} · {item.label}</option>)}</select>
      <div className="guide-sidebar-label">指南目录</div>
      <nav className="guide-toc-links" aria-label="使用指南章节目录">{guideSections.map((item) => <a aria-current={activeSection === item.id ? 'location' : undefined} className={activeSection === item.id ? 'active' : ''} href={`#${item.id}`} key={item.id} onClick={() => setActiveSection(item.id)}><span className="guide-toc-number">{item.number}</span><span className="guide-toc-copy"><b>{item.label}</b><small>{item.description}</small></span></a>)}</nav>
      <div className="guide-sidebar-bottom"><div className="guide-note"><span className="guide-note-icon">✓</span><span><b>来自真实项目</b><small>所有截图均来自实际运行的演示知识库，不是设计稿或假数据。</small></span></div></div>
    </aside>
    <main className="guide-main">
      <header className="guide-header"><div className="guide-header-title"><span>DOCUMENTATION</span><strong>使用指南</strong></div><div className="guide-header-actions"><span>本地 RAG 知识库操作手册</span><Link className="secondary-button" to="/">返回工作台</Link></div></header>
      <div className="guide-container"><article className="guide-article">
        <section className="panel guide-hero" id="guide-start">
          <span className="panel-kicker">GETTING STARTED</span><h2>五分钟了解 ZhiWeave</h2>
          <p>ZhiWeave 不是先从聊天框开始，而是把“资料怎样成为可检索知识”完整展示出来。第一次使用时，只要顺着下面五步走。</p>
          <ol className="guide-flow" aria-label="知识库构建步骤"><li><b>01</b><span>选择或创建知识库</span></li><li><b>02</b><span>抓取网页或上传文件</span></li><li><b>03</b><span>检查页面与 Chunk</span></li><li><b>04</b><span>对比检索并建立评测集</span></li><li><b>05</b><span>检查一致性并导出 ZIP</span></li></ol>
          <div className="guide-actions"><button className="primary-button" onClick={() => navigateTo('sources')} type="button">开始导入资料</button><button className="secondary-button" onClick={() => navigateTo('retrieval')} type="button">直接体验检索</button></div>
        </section>

        <section className="panel guide-section" id="guide-import">
          <span className="guide-step">01 · 建立知识库</span><h2>从网页入口或本地文档开始</h2>
          <p>选择知识库后，可以填入任意公开网站的入口页面，也可以上传 Markdown、TXT 或 PDF。网页模式会预览目标域名和父目录范围；文件模式在本机完成解析，不上传到外部模型服务。</p>
          <ul><li>爬虫只访问同域名、同目录下可发现的普通 HTML 页面，并遵守 robots.txt 与 SSRF 安全限制。</li><li>任务会依次经过读取、清洗、切片、Embedding 和写入 Qdrant；失败页面不会阻断其他页面。</li><li>任务进入 Celery 队列，支持暂停、继续、取消和失败重试，关闭页面也不会中断。</li><li>上传文件成功入库后，临时原文件会自动清理；失败任务保留原文件以支持重试。</li></ul>
          <figure><img src="/guide/01-overview.png" alt="ZhiWeave 知识库总览与网页导入区域" loading="lazy" /><figcaption>总览页同时展示真实统计、网页入口和当前处理流水线。</figcaption></figure>
          <button className="guide-link" onClick={() => navigateTo('sources')} type="button">打开数据源页面 →</button>
        </section>

        <section className="panel guide-section" id="guide-inspect">
          <span className="guide-step">02 · 检查加工结果</span><h2>不要等到问答错误时才检查数据</h2>
          <p>“数据源”用于确认页面或文件是否正确，也可以停用、重新启用、重抓、重建或异步删除文档；“Chunk 工作台”用于检查章节标题、切片边界、重叠、字符数和内容哈希。网页正文会按标题、段落、列表、代码块和表格清洗，字符重叠也会避开半个英文单词和代码块内部。重建时，Chunk 级评测目标会按文档、序号与内容哈希重新绑定；切片发生变化时则安全降级为文档级目标。</p>
          <div className="guide-gallery"><figure><img src="/guide/02-sources.png" alt="已抓取页面和来源地址列表" loading="lazy" /><figcaption>每个文档保留原始 URL、语言、状态和抓取时间。</figcaption></figure><figure><img src="/guide/03-chunks.png" alt="Chunk 工作台中的真实切片内容" loading="lazy" /><figcaption>正文 Chunk 应当可以直接阅读；向量本身不需要也不适合人工阅读。</figcaption></figure></div>
          <div className="guide-actions"><button className="secondary-button" onClick={() => navigateTo('sources')} type="button">查看数据源</button><button className="secondary-button" onClick={() => navigateTo('chunks')} type="button">查看 Chunk</button></div>
        </section>

        <section className="panel guide-section" id="guide-retrieve">
          <span className="guide-step">03 · 对比并评测检索</span><h2>先把召回质量量化，再决定是否接入聊天模型</h2>
          <p>检索实验室支持 <code>Qdrant 语义检索</code>、<code>BM25 关键词检索</code> 与 <code>RRF 混合融合</code>，并可按语言、来源、最低分过滤。结果区明确展示的是“检索证据”，不是聊天模型整理后的答案；可以查看章节、命中词、完整 Chunk 和前后文。添加“问题—期望文档”用例后，还能计算 Recall@K、MRR 和命中率。当前阶段不需要聊天 API Key。</p>
          <figure><img src="/guide/04-retrieval.png" alt="MySQL WHERE 子句的真实 Top-K 检索结果" loading="lazy" /><figcaption>问题“MySQL WHERE 子句如何筛选记录？”命中了对应教程，新版结构化索引实测最高 Cosine 约 91.8%。</figcaption></figure>
          <button className="guide-link" onClick={() => navigateTo('retrieval')} type="button">运行一次检索 →</button>
        </section>

        <section className="panel guide-section" id="guide-export">
          <span className="guide-step">04 · 运维、校验与迁移</span><h2>任务可恢复，双存储可核对，数据可迁移</h2>
          <p>任务页支持暂停、继续、取消和重试。导出页会核对 PostgreSQL Chunk 与 Qdrant Point ID、检查 Embedding 签名，并可用蓝绿重建修复；数据库只在新索引完整提交后切换，旧 Collection 清理失败不会回删当前索引。默认 E5 revision 固定到明确的 Hugging Face commit。</p>
          <div className="guide-gallery compact"><figure><img src="/guide/05-tasks.png" alt="Celery 后台任务队列" loading="lazy" /><figcaption>区分正在失败、历史失败与后续已成功。</figcaption></figure><figure><img src="/guide/06-export.png" alt="可移植知识库导出页面" loading="lazy" /><figcaption>通用 ZIP 不依赖搬运 Qdrant 内部数据库文件。</figcaption></figure></div>
          <div className="guide-actions"><button className="secondary-button" onClick={() => navigateTo('tasks')} type="button">查看任务</button><button className="secondary-button" onClick={() => navigateTo('export')} type="button">前往导出</button></div>
        </section>

        <section className="panel guide-section guide-faq" id="guide-faq">
          <span className="guide-step">FAQ</span><h2>第一次使用常见问题</h2>
          <details><summary>为什么没有聊天框？</summary><p>RAG 的核心首先是可靠检索。当前版本把数据获取、Chunk、Embedding 和召回做成可验证工作台；LLM 生成层以后可以作为可选模块接入。</p></details>
          <details><summary>检索结果为什么不是一段直接答案？</summary><p>这里显示的是从 PostgreSQL 取回的原始文本证据，Qdrant 只负责用向量找到对应 Chunk，并不存在“把向量翻译回中文”的步骤。正常的 Chunk 应当可以阅读；点击“查看前后文”可以补齐上下段。将来接入 LLM 后，才会把这些证据组织成带引用的自然语言答案。</p></details>
          <details><summary>为什么一个教程网址能抓取多个章节？</summary><p>入口页中的链接会进入广度优先队列，系统继续发现同域名、同目录的章节，直到队列为空或达到最大页数。</p></details>
          <details><summary>看到失败任务应该怎么办？</summary><p>先看它是否标注“后续已成功”。如果没有，阅读错误码与阶段信息后直接重试；长任务也可以先暂停再继续。网站拒绝抓取时，应尊重站点规则并改用有权使用的文件。</p></details>
          <details><summary>修改模型、维度或切片参数会怎样？</summary><p>这些参数决定整个向量空间，不能直接覆盖旧数据。设置页会创建新 Collection，全部文档重建成功后原子切换；切换后的旧索引清理属于独立的收尾动作。</p></details>
          <details><summary>为什么模型 revision 是一串 commit？</summary><p>固定 commit 能保证同一模型签名永远对应同一组模型权重，避免上游 main 分支更新后把两个不同向量空间误当成同一个。</p></details>
          <details><summary>导出 ZIP 后能做什么？</summary><p>可以检查 Markdown 和 JSONL、在另一台机器重建向量索引，或使用附带示例代码运行检索，不会被某个向量数据库内部格式锁死；Qdrant 快照则适合同版本的精确恢复。</p></details>
        </section>
      </article></div>
    </main>
  </div>
}
