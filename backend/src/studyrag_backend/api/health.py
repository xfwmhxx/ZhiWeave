from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from studyrag_backend.schemas.health import HealthResponse
from studyrag_backend.services.readiness import ReadinessService

router = APIRouter(prefix="/health", tags=["health"])


def get_readiness_service(request: Request) -> ReadinessService:
    return cast(ReadinessService, request.app.state.readiness_service)


@router.get("/live", response_model=HealthResponse)
async def live(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="alive",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def ready(
    readiness: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> HealthResponse | JSONResponse:
    report = await readiness.check()
    if report.status == "not_ready":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=report.model_dump(mode="json"),
        )
    return report
