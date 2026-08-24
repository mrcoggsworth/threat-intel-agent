# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY config ./config
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY alembic ./alembic
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /app/src /app/src
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/config /app/config
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic
RUN useradd --create-home --uid 10001 hermes && chmod 0555 /app/scripts/*.sh
USER hermes
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["uvicorn", "hermes_cti.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
