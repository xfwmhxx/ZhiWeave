from qdrant_client import AsyncQdrantClient

from studyrag_backend.infrastructure.vector_store import VectorStore


class QdrantManager:
    def __init__(self, url: str, *, timeout: float) -> None:
        self.client = AsyncQdrantClient(url=url, timeout=max(1, int(timeout)))
        self.vector_store = VectorStore(self.client)

    async def ping(self) -> bool:
        await self.client.get_collections()
        return True

    async def close(self) -> None:
        await self.client.close()
