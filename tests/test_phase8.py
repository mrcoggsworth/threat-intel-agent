"""Offline Phase 8 portal, public API, and private-surface tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.db.models import Report, ReportVersion
from hermes_cti.portal.contracts import (
    PortalQuery,
    PrivateDraftPage,
    PublicRelatedReports,
    PublicReportPage,
)
from hermes_cti.portal.repository import ReportRow
from hermes_cti.portal.service import PortalService
from tests.test_phase7 import _fixture


class MemoryPortalService(PortalService):
    """Representative fixture service; production uses the SQL repository."""

    def __init__(self, *, malicious: bool = False) -> None:
        super().__init__()
        bundle = _fixture()
        if malicious:
            bundle = bundle.model_copy(
                update={
                    "headline": "<script>alert(1)</script>",
                    "executive_summary": "<img src=x onerror=alert(1)>",
                }
            )
        now = datetime(2026, 8, 23, 12, tzinfo=UTC)
        self.bundle = bundle
        self.report = Report(
            id=bundle.report_id,
            public_id=bundle.public_id,
            slug=bundle.slug,
            headline=bundle.headline,
            report_type=bundle.report_type,
            severity=bundle.severity.value,
            confidence=bundle.confidence,
            state="published",
            first_published_at=now,
            last_updated_at=now,
            current_version_id=bundle.report_version_id,
            resurfaced=bundle.resurfaced,
        )
        self.version = ReportVersion(
            id=bundle.report_version_id,
            report_id=bundle.report_id,
            version=bundle.version,
            executive_summary=bundle.executive_summary,
            technical_analysis=bundle.technical_analysis,
            evidence_summary=bundle.evidence_summary,
            analytical_caveats=list(bundle.caveats),
            source_coverage={},
            generated_by=bundle.generated_by,
            validation_status="published",
            structured_content=json.loads(bundle.stable_json()),
            evidence_ids=[str(item.evidence_id) for item in bundle.evidence],
            artifact_manifest={},
            skill_versions=[],
            application_version=bundle.application_version,
        )
        self.row = ReportRow(report=self.report, version=self.version)
        self.calls = 0
        self.draft = Report(
            id=uuid4(),
            public_id="private-draft",
            slug="private-draft",
            headline="Private draft must stay private",
            report_type="threat",
            severity="high",
            confidence=0.4,
            state="draft",
            last_updated_at=now,
        )

    async def list_reports(self, query: PortalQuery) -> PublicReportPage:
        self.calls += 1
        summary = self.summary(self.row)
        if (
            query.search
            and query.search.casefold() not in summary.headline.casefold()
            or query.severities
            and summary.severity not in query.severities
        ):
            items = ()
        else:
            items = (summary,)
        start = (query.page - 1) * query.page_size
        page_items = items[start : start + query.page_size]
        return PublicReportPage(
            items=page_items,
            page=query.page,
            page_size=query.page_size,
            total=len(items),
            total_pages=1 if items else 0,
            query=query,
        )

    async def get_report(self, identifier: str):  # type: ignore[no-untyped-def]
        if identifier in {self.report.slug, self.report.public_id}:
            return self.detail(self.row)
        return None

    async def get_section(self, identifier: str, section: str):  # type: ignore[no-untyped-def]
        detail = await self.get_report(identifier)
        return getattr(detail, section, None) if detail else None

    async def related(self, entity_type: str, entity_id: str) -> PublicRelatedReports:
        return PublicRelatedReports(
            entity_type=entity_type,
            entity_id=entity_id,
            reports=(self.summary(self.row),),
        )

    async def list_drafts(self, limit: int = 100) -> PrivateDraftPage:
        return PrivateDraftPage(
            items=(),
            total=min(limit, 0),
        )


def client(service: MemoryPortalService | None = None) -> TestClient:
    settings = Settings(admin_token=SecretStr("test-admin"), database_required=False)
    return TestClient(
        create_app(settings=settings, portal_service=service or MemoryPortalService())
    )


def test_public_contract_filters_pagination_search_and_etag() -> None:
    service = MemoryPortalService()
    c = client(service)
    response = c.get("/api/v1/public/reports?q=exploitation&severity=high&page_size=1")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["slug"] == service.report.slug
    assert body["query"]["severities"] == ["high"]
    assert response.headers["cache-control"].startswith("public")
    cached = c.get(
        "/api/v1/public/reports?q=exploitation&severity=high&page_size=1",
        headers={"If-None-Match": response.headers["etag"]},
    )
    assert cached.status_code == 304


def test_public_detail_hunt_remediation_detection_and_canonical_pages() -> None:
    c = client()
    slug = "public-cve-2027-1234"
    assert c.get(f"/api/v1/public/reports/{slug}").status_code == 200
    assert c.get(f"/api/v1/public/reports/{slug}/hunt").status_code == 200
    assert c.get(f"/api/v1/public/reports/{slug}/remediation").status_code == 200
    assert c.get(f"/api/v1/public/reports/{slug}/detections").status_code == 200
    page = c.get(f"/reports/{slug}")
    assert page.status_code == 200
    assert "Executive summary" in page.text
    assert f"/reports/{slug}/hunt" in page.text


def test_analyst_api_requires_scoped_token_and_has_validation_route() -> None:
    settings = Settings(
        admin_token=SecretStr("test-admin"),
        analyst_token=SecretStr("test-analyst"),
        database_required=False,
    )
    c = TestClient(create_app(settings=settings, portal_service=MemoryPortalService()))

    assert c.get("/api/v1/analyst/runs/latest").status_code == 404
    assert (
        c.get(
            "/api/v1/analyst/runs/latest",
            headers={"X-Analyst-Token": "test-analyst"},
        ).status_code
        == 503
    )

    response = c.post(
        "/api/v1/analyst/reports/validate",
        headers={"X-Analyst-Token": "test-analyst"},
        json=_fixture().model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_drafts_are_not_public_and_private_routes_fail_closed() -> None:
    c = client()
    assert c.get("/api/v1/public/reports/private-draft").status_code == 404
    assert c.get("/api/v1/admin/drafts").status_code == 404
    assert (
        c.get("/api/v1/admin/drafts", headers={"X-Admin-Token": "wrong"}).status_code
        == 404
    )
    assert (
        c.get(
            "/api/v1/ops/version", headers={"X-Admin-Token": "test-admin"}
        ).status_code
        == 200
    )


def test_modal_accessibility_htmx_and_javascript_disabled_canonical_content() -> None:
    c = client()
    slug = "public-cve-2027-1234"
    modal = c.get(f"/partials/reports/{slug}/modal")
    assert modal.status_code == 200
    assert 'role="dialog"' in modal.text
    assert 'aria-modal="true"' in modal.text
    assert 'hx-get="/partials/reports/' in modal.text
    canonical = c.get(f"/reports/{slug}")
    assert "Threat hunting" in canonical.text
    assert "/assets/portal.js" in canonical.text


def test_malicious_report_content_is_escaped_and_security_headers_are_present() -> None:
    response = client(MemoryPortalService(malicious=True)).get(
        "/reports/public-cve-2027-1234"
    )
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "<img" not in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_query_contract_rejects_reversed_dates() -> None:
    try:
        PortalQuery(date_from="2026-08-24", date_to="2026-08-23")
    except ValueError as exc:
        assert "date_from" in str(exc)
    else:
        raise AssertionError("reversed date range was accepted")


def test_search_works_with_empty_optional_filters() -> None:
    """Empty string filter values from HTML forms must not cause 422 errors."""
    c = client()
    # The original bug: searching with an empty confidence_min field.
    response = c.get(
        "/api/v1/public/reports?q=exploitation&confidence_min=&sort=priority"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"]["confidence_min"] is None
    assert body["query"]["search"] == "exploitation"

    # All empty optional strings (browser submits these on a blank form).
    response = c.get(
        "/api/v1/public/reports"
        "?q=&confidence_min=&date_from=&date_to="
        "&severity=&change_state=&sort=priority"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"]["search"] is None
    assert body["query"]["confidence_min"] is None
    assert body["query"]["date_from"] is None
    assert body["query"]["date_to"] is None


def test_search_works_with_single_filter_only() -> None:
    """Each filter should work independently without requiring other fields."""
    c = client()

    # Search bar only
    assert c.get("/api/v1/public/reports?q=exploitation").status_code == 200

    # Severity only
    assert c.get("/api/v1/public/reports?severity=high").status_code == 200

    # Confidence only
    r = c.get("/api/v1/public/reports?confidence_min=0.5")
    assert r.status_code == 200
    assert r.json()["query"]["confidence_min"] == 0.5

    # Sort only
    r = c.get("/api/v1/public/reports?sort=newest")
    assert r.status_code == 200
    assert r.json()["query"]["sort"] == "newest"


def test_empty_filters_work_on_html_and_htmx_routes() -> None:
    """The HTML page and HTMX partial must also tolerate empty filter strings."""
    c = client()
    assert c.get("/reports?q=CVE&confidence_min=").status_code == 200
    assert c.get("/partials/reports?q=CVE&confidence_min=").status_code == 200
    assert c.get(
        "/api/v1/public/search?q=CVE&confidence_min="
    ).status_code == 200


def test_query_contract_cleans_empty_strings() -> None:
    """PortalQuery field validators should coerce empty strings to defaults."""
    q = PortalQuery(
        search="  ",
        confidence_min="",  # type: ignore[arg-type]
        date_from="",  # type: ignore[arg-type]
        date_to="",  # type: ignore[arg-type]
        sort="",  # type: ignore[arg-type]
        page="",  # type: ignore[arg-type]
        page_size="",  # type: ignore[arg-type]
    )
    assert q.search is None
    assert q.confidence_min is None
    assert q.date_from is None
    assert q.date_to is None
    assert q.sort.value == "priority"
    assert q.page == 1
    assert q.page_size == 20


def test_component_modal_partials_and_action_pills() -> None:
    c = client()
    slug = "public-cve-2027-1234"

    # Canonical report page has action-pills
    report_res = c.get(f"/reports/{slug}")
    assert report_res.status_code == 200
    assert "action-pills" in report_res.text
    assert "pill-button" in report_res.text
    assert f"/partials/reports/{slug}/component/hunt" in report_res.text
    assert f"/partials/reports/{slug}/component/remediation" in report_res.text
    assert f"/partials/reports/{slug}/component/detections" in report_res.text

    # Component modals return dialog markup with close button
    for comp in ("hunt", "remediation", "detections"):
        res = c.get(f"/partials/reports/{slug}/component/{comp}")
        assert res.status_code == 200
        assert 'role="dialog"' in res.text
        assert 'aria-modal="true"' in res.text
        assert "dialog-close" in res.text
        assert f"Open dedicated {comp} page" in res.text

        # Direct short partial path
        direct_res = c.get(f"/partials/reports/{slug}/{comp}")
        assert direct_res.status_code == 200
        assert 'role="dialog"' in direct_res.text

