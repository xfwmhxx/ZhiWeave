import type { PropsWithChildren } from 'react'
import { Link, NavLink, useLocation } from 'react-router'

import { SettingsModal } from './SettingsModal'
import { useWorkspace } from '../workspace/context'
import { navigation, type NavigationId } from '../workspace/navigation'

export function WorkspaceShell({ children }: PropsWithChildren) {
  const location = useLocation()
  const activeNav = navigation.find((item) => item.path === location.pathname)?.id ?? 'overview'
  const {
    health, showProfile, setShowProfile, setShowSettings, navigateTo, activeId,
    selectKnowledgeBase, knowledgeBases, setShowCreate, message, error, dismissNotice,
    showCreate, createKnowledgeBase, newName, setNewName, busy, configureAccess,
  } = useWorkspace()
  const pageDescription = '从网页与本地文档构建可检查、可评测、可迁移的本地向量知识库。'

  return <div className="app-shell">
    <aside className="sidebar">
      <Link className="brand" to="/" aria-label="返回知识库总览"><img className="brand-mark" src="/zhiweave-logo-v1.png" alt="" /><div><strong>ZhiWeave</strong><span>织知 · Knowledge Studio</span></div></Link>
      <select className="mobile-nav-select" value={activeNav} onChange={(event) => navigateTo(event.target.value as NavigationId)} aria-label="移动端主导航">{navigation.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
      <div className="workspace-label">工作空间</div>
      <nav aria-label="主导航">{navigation.map((item) => <NavLink className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'} end={item.path === '/'} key={item.id} onClick={() => setShowProfile(false)} to={item.path}><span className="nav-glyph" aria-hidden="true">{item.glyph}</span>{item.label}</NavLink>)}</nav>
      <div className="sidebar-bottom">
        <div className="runtime-card"><div className="runtime-head"><span className={`status-dot ${health?.status !== 'ready' ? 'offline' : ''}`} />本地运行环境</div><div className="runtime-row"><span>Embedding</span><b>本地模型</b></div><div className="runtime-row"><span>向量数据库</span><b>Qdrant</b></div></div>
        <div className="profile-wrap"><button className="profile" onClick={() => setShowProfile((value) => !value)} type="button" aria-expanded={showProfile}><span className="avatar">H</span><span><strong>Hina</strong><small>Local workspace</small></span><span className="more">···</span></button>{showProfile && <div className="profile-menu" role="menu"><strong>Hina 的本地工作空间</strong><p>数据和模型运行在当前电脑与 WSL 环境中。</p><button onClick={() => navigateTo('guide')} type="button" role="menuitem">打开使用指南</button><button onClick={() => { setShowProfile(false); setShowSettings(true) }} type="button" role="menuitem">查看项目配置</button></div>}</div>
      </div>
    </aside>
    <main>
      <header className="topbar"><select className="knowledge-select" value={activeId} onChange={(event) => selectKnowledgeBase(event.target.value)} aria-label="当前知识库"><option value="">尚未选择知识库</option>{knowledgeBases.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}</select><div className="top-actions"><span className={`service-pill ${health?.status !== 'ready' ? 'offline' : ''}`}><i />{health?.status === 'ready' ? '所有服务正常' : '等待后端服务'}</span><button className="icon-button" onClick={configureAccess} type="button" aria-label="配置 API Key">⌘</button><button className="icon-button" onClick={() => setShowSettings(true)} type="button" aria-label="项目设置">⚙</button></div></header>
      <div className="page-content">
        <section className="page-heading"><div><span className="eyebrow">{activeNav.toUpperCase()}</span><h1>{navigation.find((item) => item.id === activeNav)?.label}</h1><p>{pageDescription}</p></div><button className="secondary-button" onClick={() => setShowCreate(true)} type="button">＋ 新建知识库</button></section>
        {(message || error) && <div className={error ? 'notice error' : 'notice'}>{error || message}<button onClick={dismissNotice} type="button">×</button></div>}
        {children}
      </div>
    </main>
    {showCreate && <div className="modal-backdrop" onMouseDown={() => setShowCreate(false)}><form className="modal" onMouseDown={(event) => event.stopPropagation()} onSubmit={createKnowledgeBase}><span className="panel-kicker">NEW KNOWLEDGE BASE</span><h2>新建知识库</h2><label htmlFor="kb-name">名称</label><input id="kb-name" value={newName} onChange={(event) => setNewName(event.target.value)} autoFocus /><p>默认使用固定版本的 multilingual-e5-small、384 维、480/80 切片配置。</p><div><button className="secondary-button" onClick={() => setShowCreate(false)} type="button">取消</button><button className="primary-button" disabled={busy === 'create'} type="submit">创建</button></div></form></div>}
    <SettingsModal />
  </div>
}
