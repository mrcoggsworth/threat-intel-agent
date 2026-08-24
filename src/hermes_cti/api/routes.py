"""Phase 0 health and version routes."""

from fastapi import APIRouter, Depends, Response, status

from hermes_cti import __version__
from hermes_cti.api.dependencies import (
    get_enrichment_service,
    get_readiness_checker,
    require_admin_token,
)
from hermes_cti.db.readiness import ReadinessChecker, ReadinessResult
from hermes_cti.enrichment.service import EnrichmentService
from hermes_cti.models.contracts import ProviderHealth
from hermes_cti.models.health import (
    LivenessResponse,
    ReadinessChecks,
    ReadinessResponse,
    VersionResponse,
)

router = APIRouter()


@router.get("/health/live", response_model=LivenessResponse)
async def health_live() -> LivenessResponse:
    """Return process liveness without dependency or configuration details."""

    return LivenessResponse(status="ok")


def _response_from_result(result: ReadinessResult) -> ReadinessResponse:
    return ReadinessResponse(
        status="ok" if result.healthy else "unhealthy",
        checks=ReadinessChecks(
            configuration=result.configuration,
            database=result.database,
        ),
        message=result.message,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    response_model_exclude_none=True,
    responses={503: {"model": ReadinessResponse}},
)
async def health_ready(
    response: Response,
    checker: ReadinessChecker = Depends(get_readiness_checker),  # noqa: B008
) -> ReadinessResponse:
    """Return a controlled 503 when required configuration or DB is unavailable."""

    result = _response_from_result(await checker.check())
    if result.status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    return VersionResponse(name="hermes-cti", version=__version__)


@router.get(
    "/api/v1/admin/provider-health",
    response_model=tuple[ProviderHealth, ...],
    dependencies=[Depends(require_admin_token)],
)
async def provider_health(
    service: EnrichmentService | None = Depends(get_enrichment_service),  # noqa: B008
) -> tuple[ProviderHealth, ...]:
    """Return secret-free provider state through the authenticated private surface."""
    if service is None:
        return ()
    return service.provider_health()
