"""Explicit Alembic migration entrypoint."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from hermes_cti.core.settings import Settings


def run_migrations(settings: Settings, revision: str = "head") -> None:
    """Apply migrations explicitly; web workers never call this automatically."""

    if settings.database_url is None:
        raise ValueError("HERMES_DATABASE_URL is required for migrations")
    repository_root = Path(__file__).resolve().parents[3]
    config = Config(str(repository_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url.get_secret_value())
    command.upgrade(config, revision)
