import logging
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter, time
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from studyrag_backend.api.router import api_router
from studyrag_backend.core.config import Settings, get_settings
from studyrag_backend.core.logging import (
    bind_request_id,
    configure_logging,
    reset_request_id,
)
from studyrag_backend.core.metrics import HTTP_DURATION, HTTP_REQUESTS
from studyrag_backend.core.workspace import bind_workspace, reset_workspace
from studyrag_backend.db.session import Database
from studyrag_backend.infrastructure.embedding import EmbeddingRegistry
from studyrag_backend.infrastructure.qdrant import QdrantManager
from studyrag_backend.infrastructure.redis import RedisManager
from studyrag_backend.services.readiness import ReadinessService

logger = logging.getLogger(__name__)
_WORKSPACE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,120}$")


def _provided_api_key(request: Request) -> str | None:
    direct = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if direct:
        return direct
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _resolve_workspace(request: Request, settings: Settings) -> str | None:
    provided = _provided_api_key(request)
    if settings.workspace_api_keys:
        if not provided:
            return None
        for workspace_id, api_key in settings.workspace_api_keys.items():
            if secrets.compare_digest(provided, api_key):
                return workspace_id
        return None
    if settings.api_key:
        if not provided or not secrets.compare_digest(provided, settings.api_key):
            return None
        return settings.default_workspace_id
    requested = request.headers.get("X-Workspace-ID", settings.default_workspace_id)
    return requested if _WORKSPACE_ID.fullmatch(requested) else None


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(
            resolved_settings.database_url,
            echo=resolved_settings.database_echo,
        )
        redis = RedisManager(resolved_settings.redis_url)
        qdrant = QdrantManager(
            resolved_settings.qdrant_url,
            timeout=resolved_settings.qdrant_timeout_seconds,
        )
        application.state.database = database
        application.state.redis = redis
        application.state.qdrant = qdrant
        application.state.embedding_registry = EmbeddingRegistry(
            device=resolved_settings.embedding_device,
            batch_size=resolved_settings.embedding_batch_size,
            cache_dir=resolved_settings.model_cache_dir,
        )
        application.state.readiness_service = ReadinessService(
            service_name=resolved_settings.app_name,
            version=resolved_settings.app_version,
            timeout_seconds=resolved_settings.dependency_timeout_seconds,
            checks={
                "postgresql": database.ping,
                "redis": redis.ping,
                "qdrant": qdrant.ping,
            },
        )
        logger.info("application_started")
        try:
            yield
        finally:
            await qdrant.close()
            await redis.close()
            await database.close()
            logger.info("application_stopped")

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        if not resolved_settings.metrics_enabled:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = bind_request_id(request_id)
        workspace_id = _resolve_workspace(request, resolved_settings)
        workspace_token = bind_workspace(workspace_id or resolved_settings.default_workspace_id)
        started = perf_counter()
        try:
            is_cors_preflight = (
                request.method == "OPTIONS"
                and "origin" in request.headers
                and "access-control-request-method" in request.headers
            )
            if not is_cors_preflight and workspace_id is None and request.url.path not in {
                f"{resolved_settings.api_prefix}/health/live",
                f"{resolved_settings.api_prefix}/health/ready",
            }:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "a valid API key is required"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if (
                not is_cors_preflight
                and resolved_settings.environment != "test"
                and request.url.path.startswith(resolved_settings.api_prefix)
                and not request.url.path.endswith(("/health/live", "/health/ready"))
            ):
                redis = cast(RedisManager, application.state.redis)
                bucket = int(time() // 60)
                key = f"rate:{workspace_id}:{bucket}"
                count = await redis.client.incr(key)
                if count == 1:
                    await redis.client.expire(key, 70)
                if count > resolved_settings.rate_limit_per_minute:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "rate limit exceeded"},
                        headers={"Retry-After": "60"},
                    )
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Workspace-ID"] = workspace_id or ""
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            duration = perf_counter() - started
            HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
            HTTP_DURATION.labels(request.method, route_path).observe(duration)
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return response
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            raise
        finally:
            reset_workspace(workspace_token)
            reset_request_id(token)

    application.include_router(api_router, prefix=resolved_settings.api_prefix)
    return application


app = create_app()
