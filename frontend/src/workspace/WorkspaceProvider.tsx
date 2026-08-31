import type { PropsWithChildren } from 'react'

import { WorkspaceContext } from './context'
import type { WorkspaceController } from './useWorkspaceController'

export function WorkspaceProvider({ value, children }: PropsWithChildren<{ value: WorkspaceController }>) {
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
