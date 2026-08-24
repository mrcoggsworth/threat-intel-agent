"""PostgreSQL readiness probe used by the private readiness surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from hermes_cti.core.settings import Settings
from hermes_cti.models.health import CheckStatus


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Internal typed result for a readiness dependency check."""

    configuration: CheckStatus
    database: CheckStatus
    message: str | None = None

    @property
    def healthy(self) -> bool:
        return self.configuration == "ok" and self.database in {"ok", "not_configured"}


class ReadinessChecker(Protocol):
    async def check(self) -> ReadinessResult:
        """Return a safe, non-secret readiness result."""


class DatabaseReadinessChecker:
    """Check required configuration and issue a lightweight DB query."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check(self) -> ReadinessResult:
        database_url = self.settings.database_url
        if database_url is None:
            if self.settings.database_required:
                return ReadinessResult(
                    configuration="unavailable",
                    database="not_configured",
                    message="required database configuration is missing",
                )
            return ReadinessResult(
                configuration="ok", database="not_configured", message=None
            )

        engine = create_async_engine(
            database_url.get_secret_value(),
            connect_args={"timeout": self.settings.database_connect_timeout_seconds},
            pool_pre_ping=True,
        )
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError, TimeoutError):
            return ReadinessResult(
                configuration="ok",
                database="unavailable",
                message="database connectivity check failed",
            )
        finally:
            await engine.dispose()
        return ReadinessResult(configuration="ok", database="ok")
