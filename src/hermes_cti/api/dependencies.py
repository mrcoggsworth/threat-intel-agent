"""FastAPI dependency providers."""

import secrets
from typing import cast

from fastapi import Header, HTTPException, Request

from hermes_cti.db.readiness import ReadinessChecker
from hermes_cti.enrichment.service import EnrichmentService
from hermes_cti.portal.service import PortalService


def get_readiness_checker(request: Request) -> ReadinessChecker:
    """Resolve the checker from application state; tests can override this."""

    return cast(ReadinessChecker, request.app.state.readiness_checker)


def get_enrichment_service(request: Request) -> EnrichmentService | None:
    """Resolve the private enrichment service from application state."""
    return cast(EnrichmentService | None, request.app.state.enrichment_service)


def get_portal_service(request: Request) -> PortalService:
    """Resolve the public projection service; tests may replace this dependency."""

    return cast(PortalService, request.app.state.portal_service)


def require_admin_token(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Keep provider health private and fail closed when no admin token is configured.

    Missing or invalid credentials intentionally look like a missing route.
    """
    settings = request.app.state.settings
    configured = settings.admin_token
    if (
        configured is None
        or x_admin_token is None
        or not secrets.compare_digest(x_admin_token, configured.get_secret_value())
    ):
        raise HTTPException(status_code=404, detail="not found")
