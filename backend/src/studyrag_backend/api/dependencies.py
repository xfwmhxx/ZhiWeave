from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from studyrag_backend.core.config import Settings
from studyrag_backend.core.workspace import current_workspace
from studyrag_backend.db.session import get_db_session
from studyrag_backend.models.knowledge_base import KnowledgeBase

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def request_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_knowledge_base(
    session: AsyncSession, knowledge_base_id: UUID, *, allow_deleting: bool = False
) -> KnowledgeBase:
    knowledge_base = await session.get(KnowledgeBase, knowledge_base_id)
    if (
        knowledge_base is None
        or knowledge_base.workspace_id != current_workspace()
        or (knowledge_base.status.value == "deleting" and not allow_deleting)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    return knowledge_base
