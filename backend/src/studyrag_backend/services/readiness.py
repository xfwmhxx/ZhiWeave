import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from studyrag_backend.schemas.health import ComponentHealth, HealthResponse

Check = Callable[[], Awaitable[bool]]
logger = logging.getLogger(__name__)


class ReadinessService:
    def __init__(
        self,
        *,
        service_name: str,
        version: str,
        timeout_seconds: float,
        checks: dict[str, Check],
    ) -> None:
        self.service_name = service_name
        self.version = version
        self.timeout_seconds = timeout_seconds
        self.checks = checks

    async def _run_check(self, name: str, check: Check) -> tuple[str, ComponentHealth]:
        started = perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                healthy = await check()
            if not healthy:
                raise RuntimeError("dependency returned an unhealthy result")
        except Exception as exc:  # Dependency failures must become readiness data, not API errors.
            latency_ms = round((perf_counter() - started) * 1000, 2)
            logger.warning(
                "dependency_check_failed",
                extra={"component": name},
                exc_info=True,
            )
            return name, ComponentHealth(
                status="down",
                latency_ms=latency_ms,
                detail=type(exc).__name__,
            )
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return name, ComponentHealth(status="up", latency_ms=latency_ms)

    async def check(self) -> HealthResponse:
        results = await asyncio.gather(
            *(self._run_check(name, check) for name, check in self.checks.items())
        )
        checks = dict(results)
        ready = all(component.status == "up" for component in checks.values())
        return HealthResponse(
            status="ready" if ready else "not_ready",
            service=self.service_name,
            version=self.version,
            checks=checks,
        )
