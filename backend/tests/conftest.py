from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from studyrag_backend.core.config import Settings
from studyrag_backend.main import create_app


class FakeDatabase:
    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeRedis:
    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeQdrant:
    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", dependency_timeout_seconds=0.1, _env_file=None)


@pytest.fixture
def app(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr("studyrag_backend.main.Database", lambda *_args, **_kwargs: FakeDatabase())
    monkeypatch.setattr("studyrag_backend.main.RedisManager", lambda *_args, **_kwargs: FakeRedis())
    monkeypatch.setattr(
        "studyrag_backend.main.QdrantManager", lambda *_args, **_kwargs: FakeQdrant()
    )
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
