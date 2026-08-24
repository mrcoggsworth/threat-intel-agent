"""Small structured JSON logging setup with correlation and redaction."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from hermes_cti.core.settings import Settings

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "hermes_request_id", default="-"
)
_run_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "hermes_run_id", default="-"
)


def new_correlation_id() -> str:
    """Create a short, log-safe correlation identifier."""

    return uuid.uuid4().hex


def set_request_id(value: str) -> contextvars.Token[str]:
    return _request_id.set(value)


def set_run_id(value: str) -> contextvars.Token[str]:
    return _run_id.set(value)


def reset_request_id(token: contextvars.Token[str]) -> None:
    _request_id.reset(token)


def reset_run_id(token: contextvars.Token[str]) -> None:
    _run_id.reset(token)


class SecretRedactor:
    """Replace configured secret values and common secret-shaped values."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._secrets = tuple(secret for secret in secrets if len(secret) >= 4)
        self._secret_pattern = re.compile(
            r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*([^\s,;]+)"
        )

    def redact(self, value: str) -> str:
        redacted = value
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        return self._secret_pattern.sub(r"\1=[REDACTED]", redacted)


class JSONFormatter(logging.Formatter):
    """Render log records as stable JSON objects."""

    def __init__(self, redactor: SecretRedactor) -> None:
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.redactor.redact(record.getMessage()),
            "request_id": _request_id.get(),
            "run_id": _run_id.get(),
        }
        for key in (
            "event",
            "status",
            "component",
            "source_id",
            "error_classification",
            "retry_count",
        ):
            if hasattr(record, key):
                payload[key] = self.redactor.redact(str(getattr(record, key)))
        return json.dumps(payload, sort_keys=True)


def configure_logging(settings: Settings) -> None:
    """Configure one redacting JSON stream handler for the application."""

    secret_values = [
        value.get_secret_value()
        for value in (settings.database_url, settings.secret_key)
        if value is not None
    ]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(SecretRedactor(secret_values)))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
