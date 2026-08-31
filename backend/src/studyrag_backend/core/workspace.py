from contextvars import ContextVar, Token

workspace_context: ContextVar[str] = ContextVar("workspace_id", default="local")


def bind_workspace(workspace_id: str) -> Token[str]:
    return workspace_context.set(workspace_id)


def reset_workspace(token: Token[str]) -> None:
    workspace_context.reset(token)


def current_workspace() -> str:
    return workspace_context.get()
