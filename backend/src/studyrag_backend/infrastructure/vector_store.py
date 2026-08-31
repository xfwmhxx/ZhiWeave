from dataclasses import dataclass
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models


@dataclass(frozen=True, slots=True)
class VectorPoint:
    id: UUID
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    point_id: UUID
    score: float
    payload: dict[str, Any]


class VectorStore:
    def __init__(self, client: AsyncQdrantClient) -> None:
        self.client = client

    async def ensure_collection(self, name: str, dimension: int) -> None:
        if not await self.client.collection_exists(name):
            await self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
        else:
            info = await self.client.get_collection(name)
            vectors = info.config.params.vectors
            actual_dimension = getattr(vectors, "size", None)
            if actual_dimension != dimension:
                raise RuntimeError(
                    f"vector collection dimension mismatch: expected={dimension}, "
                    f"actual={actual_dimension}"
                )
        for field in ("knowledge_base_id", "document_id"):
            await self.client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    async def delete_document_points(self, collection: str, document_id: UUID) -> None:
        if not await self.client.collection_exists(collection):
            return
        await self.client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def upsert(self, collection: str, points: list[VectorPoint]) -> None:
        if not points:
            return
        await self.client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(id=str(point.id), vector=point.vector, payload=point.payload)
                for point in points
            ],
            wait=True,
        )

    async def delete_collection(self, collection: str) -> None:
        if await self.client.collection_exists(collection):
            await self.client.delete_collection(collection_name=collection)

    async def delete_points(self, collection: str, point_ids: set[UUID]) -> None:
        if not point_ids or not await self.client.collection_exists(collection):
            return
        await self.client.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=[str(point_id) for point_id in point_ids]),
            wait=True,
        )

    async def update_document_payload(
        self, collection: str, document_id: UUID, payload: dict[str, Any]
    ) -> None:
        if not await self.client.collection_exists(collection):
            raise RuntimeError("vector collection does not exist")
        await self.client.set_payload(
            collection_name=collection,
            payload=payload,
            points=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=str(document_id))
                    )
                ]
            ),
            wait=True,
        )

    async def collection_point_ids(self, collection: str) -> set[UUID]:
        if not await self.client.collection_exists(collection):
            return set()
        point_ids: set[UUID] = set()
        offset: Any | None = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            point_ids.update(UUID(str(point.id)) for point in points)
            if offset is None:
                break
        return point_ids

    async def search(
        self,
        *,
        collection: str,
        knowledge_base_id: UUID,
        vector: list[float],
        limit: int,
        score_threshold: float | None = None,
        language: str | None = None,
        source_type: str | None = None,
    ) -> list[VectorSearchHit]:
        must = [
            models.FieldCondition(
                key="knowledge_base_id",
                match=models.MatchValue(value=str(knowledge_base_id)),
            ),
            models.FieldCondition(key="enabled", match=models.MatchValue(value=True)),
        ]
        if language:
            must.append(
                models.FieldCondition(key="language", match=models.MatchValue(value=language))
            )
        if source_type:
            must.append(
                models.FieldCondition(key="source_type", match=models.MatchValue(value=source_type))
            )
        result = await self.client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=models.Filter(must=must),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        return [
            VectorSearchHit(
                point_id=UUID(str(point.id)),
                score=point.score,
                payload=dict(point.payload or {}),
            )
            for point in result.points
        ]
