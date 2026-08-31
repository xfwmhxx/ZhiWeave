from fastapi import APIRouter

from studyrag_backend.api.documents import router as documents_router
from studyrag_backend.api.health import router as health_router
from studyrag_backend.api.knowledge_bases import router as knowledge_bases_router
from studyrag_backend.api.retrieval import router as retrieval_router
from studyrag_backend.api.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(documents_router)
api_router.include_router(tasks_router)
api_router.include_router(retrieval_router)
