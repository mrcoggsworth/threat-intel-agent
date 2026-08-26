"""Shared SQLAlchemy registry and audit columns for all persistence models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative registry for all Hermes persistence tables."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    record_status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False
    )
    created_by_origin: Mapped[str] = mapped_column(
        String(64), default="deterministic_service", nullable=False
    )
