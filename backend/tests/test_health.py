from fastapi import FastAPI
from httpx import AsyncClient

from studyrag_backend.services.readiness import ReadinessService


async def healthy() -> bool:
    return True


async def unhealthy() -> bool:
    return False


async def test_liveness_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json() == {
        "status": "alive",
        "service": "ZhiWeave API",
        "version": "0.1.0",
        "checks": {},
    }


async def test_readiness_returns_dependency_details(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgresql"]["status"] == "up"
    assert body["checks"]["redis"]["status"] == "up"
    assert body["checks"]["qdrant"]["status"] == "up"


async def test_readiness_returns_503_when_dependency_is_down(
    client: AsyncClient, app: FastAPI
) -> None:
    app.state.readiness_service = ReadinessService(
        service_name="ZhiWeave API",
        version="0.1.0",
        timeout_seconds=0.1,
        checks={"postgresql": healthy, "redis": unhealthy},
    )

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"]["status"] == "down"
