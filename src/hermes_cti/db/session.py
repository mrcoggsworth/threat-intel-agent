"""Async PostgreSQL engine and transaction management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hermes_cti.core.settings import Settings

DEFAULT_POOL_SIZE: Final = 5


class Database:
    """Application-owned async engine and session factory."""

    def __init__(
        self,
        settings: Settings,
        *,
        engine: AsyncEngine | None = None,
    ) -> None:
        if engine is not None:
            self.engine = engine
        else:
            if settings.database_url is None:
                raise ValueError("database URL is required for database operations")
            self.engine = create_async_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,
                pool_size=settings.database_pool_size or DEFAULT_POOL_SIZE,
                max_overflow=settings.database_max_overflow,
                connect_args={
                    "timeout": settings.database_connect_timeout_seconds,
                },
            )
        self.sessions = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session whose caller controls the transaction boundary."""

        async with self.sessions() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and commit only after the full unit succeeds."""

        async with self.sessions() as session, session.begin():
            yield session

    async def dispose(self) -> None:
        """Dispose all pooled connections."""

        await self.engine.dispose()
