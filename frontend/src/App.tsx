import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import './App.css'
import { WorkspaceShell } from './components/WorkspaceShell'
import { GuidePage } from './pages/GuidePage'
import {
  ChunksPage,
  ExportPage,
  OverviewPage,
  RetrievalPage,
  SourcesPage,
  TasksPage,
} from './pages/WorkspacePages'
import { WorkspaceProvider } from './workspace/WorkspaceProvider'
import { useWorkspaceController } from './workspace/useWorkspaceController'

function WorkspaceRoute({ children }: { children: ReactNode }) {
  return <WorkspaceShell>{children}</WorkspaceShell>
}

function App() {
  const workspace = useWorkspaceController()

  return <WorkspaceProvider value={workspace}>
    <Routes>
      <Route path="/guide" element={<GuidePage />} />
      <Route path="/" element={<WorkspaceRoute><OverviewPage /></WorkspaceRoute>} />
      <Route path="/sources" element={<WorkspaceRoute><SourcesPage /></WorkspaceRoute>} />
      <Route path="/chunks" element={<WorkspaceRoute><ChunksPage /></WorkspaceRoute>} />
      <Route path="/retrieval" element={<WorkspaceRoute><RetrievalPage /></WorkspaceRoute>} />
      <Route path="/tasks" element={<WorkspaceRoute><TasksPage /></WorkspaceRoute>} />
      <Route path="/export" element={<WorkspaceRoute><ExportPage /></WorkspaceRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </WorkspaceProvider>
}

export default App
