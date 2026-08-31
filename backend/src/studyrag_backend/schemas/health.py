from typing import Literal

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    status: Literal["up", "down"]
    latency_ms: float = Field(ge=0)
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["alive", "ready", "not_ready"]
    service: str
    version: str
    checks: dict[str, ComponentHealth] = Field(default_factory=dict)
