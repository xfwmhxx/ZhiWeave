import { createContext, useContext } from 'react'

import type { WorkspaceController } from './useWorkspaceController'

export const WorkspaceContext = createContext<WorkspaceController | null>(null)

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return context
}
