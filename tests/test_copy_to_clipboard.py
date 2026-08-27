"""Tests for detection copy-to-clipboard UI rendering and JS handlers."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from tests.test_phase8 import MemoryPortalService


def test_detections_modal_partial_renders_copy_buttons() -> None:
    portal_service = MemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/detections"
        )
        assert response.status_code == 200
        html = response.text

        # Verify copy button presence and attributes
        assert "data-copy-target" in html
        assert 'aria-label="Copy detection rule content"' in html
        assert "copy-button" in html
        assert "copy-icon" in html
        assert "copy-label" in html
        assert "Copy" in html


def test_dedicated_detections_page_renders_copy_buttons() -> None:
    portal_service = MemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(f"/reports/{portal_service.report.slug}/detections")
        assert response.status_code == 200
        html = response.text

        assert "data-copy-target" in html
        assert "copy-button" in html
        assert "Copy" in html


def test_portal_js_contains_clipboard_copy_handler() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "hermes_cti" / "portal" / "static"
    portal_js = (static_dir / "portal.js").read_text(encoding="utf-8")

    assert "data-copy-target" in portal_js
    assert "copyText" in portal_js
    assert "navigator.clipboard" in portal_js
    assert "Copied!" in portal_js
