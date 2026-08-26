"""FastAPI application factory and API console entrypoint."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from hermes_cti import __version__
from hermes_cti.analyst.routes import router as analyst_router
from hermes_cti.api.routes import router
from hermes_cti.core.logging import (
    configure_logging,
    new_correlation_id,
    reset_request_id,
    set_request_id,
)
from hermes_cti.core.settings import Settings, load_settings
from hermes_cti.db.readiness import DatabaseReadinessChecker, ReadinessChecker
from hermes_cti.db.session import Database
from hermes_cti.enrichment.service import EnrichmentService
from hermes_cti.portal.routes import router as portal_router
from hermes_cti.portal.security import PortalSecurityHeadersMiddleware
from hermes_cti.portal.service import PortalService, PortalUnavailableError


def create_app(
    settings: Settings | None = None,
    readiness_checker: ReadinessChecker | None = None,
    enrichment_service: EnrichmentService | None = None,
    portal_service: PortalService | None = None,
) -> FastAPI:
    """Build the API with explicit settings and replaceable dependencies."""

    resolved_settings = settings or load_settings()
    configure_logging(resolved_settings)
    app = FastAPI(
        title="Hermes CTI",
        version=__version__,
        description="Public CTI service foundation; feature pipelines are phased.",
    )
    app.state.settings = resolved_settings
    app.state.readiness_checker = readiness_checker or DatabaseReadinessChecker(
        resolved_settings
    )
    app.state.enrichment_service = enrichment_service
    database = (
        Database(resolved_settings)
        if resolved_settings.database_url is not None
        else None
    )
    app.state.database = database
    app.state.portal_service = portal_service or PortalService(database=database)
    if portal_service is not None and database is None:
        app.state.database = getattr(portal_service, "database", None)
    app.add_middleware(PortalSecurityHeadersMiddleware)
    app.mount(
        "/assets",
        StaticFiles(
            directory=Path(__file__).resolve().parents[1] / "portal" / "static"
        ),
        name="portal-assets",
    )
    app.include_router(router)
    app.include_router(analyst_router)
    app.include_router(portal_router)

    @app.exception_handler(PortalUnavailableError)
    async def portal_unavailable(
        request: Request, exc: PortalUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "portal is unavailable"}
        )

    @app.middleware("http")
    async def correlation_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        header_name = resolved_settings.request_id_header
        candidate = request.headers.get(header_name, "")
        request_id = (
            candidate
            if len(candidate) <= 128 and candidate.isprintable() and candidate
            else new_correlation_id()
        )
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[header_name] = request_id
        return response

    return app


app = create_app()


def run() -> None:
    """Run the API with Uvicorn for the declared console script."""

    import uvicorn

    uvicorn.run("hermes_cti.api.main:app", host="0.0.0.0", port=8000)
