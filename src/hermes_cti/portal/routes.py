"""HTML, HTMX, public JSON, and authenticated private portal routes."""
# ruff: noqa: B008

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from hermes_cti.api.dependencies import get_portal_service, require_admin_token
from hermes_cti.models.contracts import Remediation, Severity, ThreatHunt
from hermes_cti.portal.contracts import (
    PortalQuery,
    PrivateDraftPage,
    PublicDetectionPage,
    PublicRelatedReports,
    PublicReportDetail,
    PublicReportPage,
    ReportChangeState,
    ReportSort,
)
from hermes_cti.portal.entity_contracts import PublicEntity, PublicRelationshipPage
from hermes_cti.portal.service import PortalService

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


def _query(
    q: str | None = Query(default=None, max_length=200),
    severity: Annotated[list[Severity | str] | None, Query()] = None,
    confidence_min: float | str | None = Query(default=None),
    date_from: date | str | None = Query(default=None),
    date_to: date | str | None = Query(default=None),
    change_state: Annotated[list[ReportChangeState | str] | None, Query()] = None,
    sort: ReportSort | str = Query(default=ReportSort.PRIORITY),
    page: int | str = Query(default=1),
    page_size: int | str = Query(default=20),
) -> PortalQuery:
    try:
        return PortalQuery(
            search=q,
            severities=severity,
            confidence_min=confidence_min,
            date_from=date_from,
            date_to=date_to,
            change_states=change_state,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except ValidationError as exc:
        errors: list[Any] = []
        for err in exc.errors():
            err_dict = dict(err)
            raw_loc: tuple[str | int, ...] = err_dict.get("loc", ())  # type: ignore[assignment]
            err_dict["loc"] = ("query", *raw_loc)
            errors.append(err_dict)
        raise RequestValidationError(errors=errors) from exc
    except ValueError as exc:
        raise RequestValidationError(
            errors=[{"loc": ("query",), "msg": str(exc), "type": "value_error"}]
        ) from exc


def _etag_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f'"{hashlib.sha256(encoded).hexdigest()}"'


def _json_response(request: Request, payload: Any, *, max_age: int = 60) -> Response:
    body = jsonable_encoder(payload)
    etag = _etag_payload(body)
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag}
        )
    return JSONResponse(
        content=body,
        headers={
            "ETag": etag,
            "Cache-Control": f"public, max-age={max_age}, stale-while-revalidate=300",
        },
    )


async def _public_detail(service: PortalService, identifier: str) -> PublicReportDetail:
    detail = await service.get_report(identifier)
    if detail is None:
        raise HTTPException(status_code=404, detail="report not found")
    return detail


def _context(request: Request, page: Any = None, detail: Any = None) -> dict[str, Any]:
    return {"request": request, "page": page, "detail": detail}


@router.get("/api/v1/public/reports", response_model=PublicReportPage)
async def public_reports(
    request: Request,
    query: PortalQuery = Depends(_query),
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    return _json_response(request, await service.list_reports(query))


@router.get("/api/v1/public/search", response_model=PublicReportPage)
async def public_search(
    request: Request,
    query: PortalQuery = Depends(_query),
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    return _json_response(request, await service.list_reports(query))


@router.get("/api/v1/public/reports/{identifier}", response_model=PublicReportDetail)
async def public_report(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    return _json_response(request, await _public_detail(service, identifier))


@router.get("/api/v1/public/reports/{identifier}/hunt", response_model=ThreatHunt)
async def public_hunt(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    detail = await _public_detail(service, identifier)
    if detail.hunt is None:
        raise HTTPException(status_code=404, detail="hunt not available")
    return _json_response(request, detail.hunt)


@router.get(
    "/api/v1/public/reports/{identifier}/remediation",
    response_model=Remediation,
)
async def public_remediation(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    detail = await _public_detail(service, identifier)
    if detail.remediation is None:
        raise HTTPException(status_code=404, detail="remediation not available")
    return _json_response(request, detail.remediation)


@router.get(
    "/api/v1/public/reports/{identifier}/detections",
    response_model=PublicDetectionPage,
)
async def public_detections(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    detail = await _public_detail(service, identifier)
    return _json_response(
        request,
        {
            "report": detail.summary.model_dump(mode="json"),
            "detections": detail.detections,
        },
    )


@router.get(
    "/api/v1/public/entities/{entity_type}/{identifier}", response_model=PublicEntity
)
async def public_entity(
    request: Request,
    entity_type: str,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    entity = await service.get_public_entity(entity_type, identifier)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    body = entity.model_dump(mode="json")
    if entity.vulnerability is None:
        body.pop("vulnerability", None)
    return _json_response(request, body)


@router.get("/api/v1/public/relationships", response_model=PublicRelationshipPage)
async def public_relationships(
    request: Request,
    entity_type: str | None = Query(default=None, max_length=64),
    identifier: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=100, ge=1, le=100),
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    if (entity_type is None) != (identifier is None):
        raise HTTPException(
            status_code=400,
            detail="entity_type and identifier must be supplied together",
        )
    return _json_response(
        request,
        await service.public_relationships(
            entity_type=entity_type, identifier=identifier, limit=limit
        ),
    )


@router.get(
    "/api/v1/public/related/{entity_type}/{entity_id}",
    response_model=PublicRelatedReports,
)
async def public_related(
    request: Request,
    entity_type: str,
    entity_id: str,
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    return _json_response(request, await service.related(entity_type, entity_id))


@router.get("/partials/reports", response_class=HTMLResponse)
async def report_list_partial(
    request: Request,
    query: PortalQuery = Depends(_query),
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    page = await service.list_reports(query)
    return templates.TemplateResponse(
        request=request,
        name="partials/report_list.html",
        context=_context(request, page),
    )


@router.get("/partials/reports/{identifier}/modal", response_class=HTMLResponse)
async def report_modal_partial(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    detail = await _public_detail(service, identifier)
    return templates.TemplateResponse(
        request=request,
        name="partials/report_modal.html",
        context=_context(request, detail=detail),
    )


@router.get(
    "/partials/reports/{identifier}/component/{component}", response_class=HTMLResponse
)
@router.get("/partials/reports/{identifier}/hunt", response_class=HTMLResponse)
@router.get("/partials/reports/{identifier}/remediation", response_class=HTMLResponse)
@router.get("/partials/reports/{identifier}/detections", response_class=HTMLResponse)
async def report_component_modal_partial(
    request: Request,
    identifier: str,
    component: str | None = None,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    if component is None:
        component = request.url.path.rsplit("/", 1)[-1]
    detail = await _public_detail(service, identifier)
    value = getattr(detail, component, None)
    if value is None or (isinstance(value, tuple) and not value):
        raise HTTPException(status_code=404, detail=f"{component} not available")
    return templates.TemplateResponse(
        request=request,
        name="partials/component_modal.html",
        context={
            "request": request,
            "detail": detail,
            "component": component,
            "value": value,
        },
    )


@router.get(
    "/partials/reports/{identifier}/section/{section}", response_class=HTMLResponse
)
async def report_section_partial(
    request: Request,
    identifier: str,
    section: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    value = await service.get_section(identifier, section)
    if value is None:
        raise HTTPException(status_code=404, detail="report section not found")
    return templates.TemplateResponse(
        request=request,
        name="partials/section.html",
        context={"request": request, "section": section, "value": value},
    )


@router.get("/partials/filter-options", response_class=HTMLResponse)
async def filter_options(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/filter_options.html",
        context={"request": request},
    )


@router.get("/partials/related/{entity_type}/{entity_id}", response_class=HTMLResponse)
async def related_partial(
    request: Request,
    entity_type: str,
    entity_id: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    related = await service.related(entity_type, entity_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/related.html",
        context={"request": request, "related": related},
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    query: PortalQuery = Depends(_query),
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    page = await service.list_reports(query)
    return templates.TemplateResponse(
        request=request, name="reports.html", context=_context(request, page)
    )


@router.get("/reports/{identifier}", response_class=HTMLResponse)
async def report_page(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    detail = await _public_detail(service, identifier)
    return templates.TemplateResponse(
        request=request, name="report.html", context=_context(request, detail=detail)
    )


async def _component_page(
    request: Request, identifier: str, component: str, service: PortalService
) -> HTMLResponse:
    detail = await _public_detail(service, identifier)
    value = getattr(detail, component)
    if value is None or (isinstance(value, tuple) and not value):
        raise HTTPException(status_code=404, detail=f"{component} not available")
    return templates.TemplateResponse(
        request=request,
        name="component.html",
        context={
            "request": request,
            "detail": detail,
            "component": component,
            "value": value,
        },
    )


@router.get("/reports/{identifier}/hunt", response_class=HTMLResponse)
async def hunt_page(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    return await _component_page(request, identifier, "hunt", service)


@router.get("/reports/{identifier}/remediation", response_class=HTMLResponse)
async def remediation_page(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    return await _component_page(request, identifier, "remediation", service)


@router.get("/reports/{identifier}/detections", response_class=HTMLResponse)
async def detections_page(
    request: Request,
    identifier: str,
    service: PortalService = Depends(get_portal_service),
) -> HTMLResponse:  # noqa: B008
    return await _component_page(request, identifier, "detections", service)


@router.get(
    "/api/v1/admin/drafts",
    response_model=PrivateDraftPage,
    dependencies=[Depends(require_admin_token)],
)
async def admin_drafts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    service: PortalService = Depends(get_portal_service),
) -> Response:  # noqa: B008
    return _json_response(request, await service.list_drafts(limit), max_age=0)


@router.get("/api/v1/ops/metrics", dependencies=[Depends(require_admin_token)])
async def ops_metrics() -> dict[str, str]:
    return {
        "scope": "private",
        "status": "available",
        "note": "bounded metrics are not persisted in Phase 8",
    }


@router.get("/api/v1/ops/readiness", dependencies=[Depends(require_admin_token)])
async def ops_readiness(request: Request) -> Any:
    return await request.app.state.readiness_checker.check()


@router.get("/api/v1/ops/version", dependencies=[Depends(require_admin_token)])
async def ops_version(request: Request) -> dict[str, str]:
    return {"scope": "private", "version": request.app.state.settings.app_version}


@router.get("/api/v1/ops/last-success", dependencies=[Depends(require_admin_token)])
async def ops_last_success(request: Request) -> dict[str, None | str]:
    database = getattr(request.app.state.portal_service, "database", None)
    if database is None:
        return {"scope": "private", "last_success": None}
    from hermes_cti.db.repositories import RunRepository

    async with database.session() as session:
        last = await RunRepository().last_successful(session)
    return {
        "scope": "private",
        "last_success": last.completed_at.isoformat()
        if last and last.completed_at
        else None,
    }


@router.get(
    "/api/v1/ops/scheduler-heartbeat",
    dependencies=[Depends(require_admin_token)],
)
async def ops_scheduler_heartbeat(request: Request) -> dict[str, None | str]:
    heartbeat_file = request.app.state.settings.scheduler_heartbeat_file
    if not heartbeat_file:
        return {"scope": "private", "heartbeat": None}
    from pathlib import Path

    path = Path(heartbeat_file)
    try:
        heartbeat = path.read_text(encoding="utf-8").strip() or None
    except OSError:
        heartbeat = None
    return {"scope": "private", "heartbeat": heartbeat}
