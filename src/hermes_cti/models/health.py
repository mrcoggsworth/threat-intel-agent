"""Typed health and readiness response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CheckStatus = Literal["ok", "unavailable", "not_configured"]


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration: CheckStatus
    database: CheckStatus


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "unhealthy"]
    checks: ReadinessChecks
    message: str | None = Field(default=None, max_length=200)


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
