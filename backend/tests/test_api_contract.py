from httpx import AsyncClient

from studyrag_backend.core.config import Settings


async def test_openapi_exposes_complete_management_contract(client: AsyncClient) -> None:
    document = (await client.get("/openapi.json")).json()
    paths = document["paths"]

    assert "/api/v1/knowledge-bases/{knowledge_base_id}/imports/files" in paths
    assert "/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/refetch" in paths
    assert "/api/v1/knowledge-bases/{knowledge_base_id}/tasks/{task_id}/retry" in paths
    assert "/api/v1/knowledge-bases/{knowledge_base_id}/consistency/repair" in paths
    assert "/api/v1/knowledge-bases/{knowledge_base_id}/evaluation-runs" in paths


async def test_cors_preflight_is_not_blocked_by_api_key_auth(
    client: AsyncClient, settings: Settings
) -> None:
    settings.api_key = "test-api-key"

    response = await client.options(
        "/api/v1/knowledge-bases",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()
