"""Tests for multi-theme options, rendering, and stylesheets."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from tests.test_phase8 import MemoryPortalService

EXPECTED_THEMES = [
    "traditional-light",
    "traditional-dark",
    "cyberpunk",
    "synthwave",
    "tokyo-night",
    "darcula",
    "monokai",
    "synthwave-metal",
    "matrix",
]


def test_portal_html_renders_theme_selector_with_all_nine_themes() -> None:
    portal_service = MemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get("/reports")
        assert response.status_code == 200
        html = response.text

        # Verify selector element
        assert 'id="theme-selector"' in html
        assert 'data-theme="traditional-light"' in html

        # Verify all 9 themes are available options
        for theme in EXPECTED_THEMES:
            assert f'value="{theme}"' in html

        # Verify theme display labels
        assert "Traditional Light" in html
        assert "Traditional Dark" in html
        assert "Cyberpunk" in html
        assert "Synthwave" in html
        assert "Tokyo Night" in html
        assert "Darcula" in html
        assert "Monokai" in html
        assert "Synthwave Metal / Teal" in html
        assert "Matrix Green" in html


def test_theme_css_definitions_present_in_input_and_compiled_css() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "hermes_cti" / "portal" / "static"
    input_css = (static_dir / "input.css").read_text(encoding="utf-8")
    portal_css = (static_dir / "portal.css").read_text(encoding="utf-8")

    for theme in EXPECTED_THEMES:
        assert f'data-theme="{theme}"' in input_css
        assert (
            f'data-theme="{theme}"' in portal_css or f"data-theme={theme}" in portal_css
        )


def test_portal_static_js_contains_theme_bootstrap() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "hermes_cti" / "portal" / "static"
    portal_js = (static_dir / "portal.js").read_text(encoding="utf-8")

    assert "hermes-theme" in portal_js
    assert "applySavedTheme" in portal_js
    assert "initThemeSelector" in portal_js

    for theme in EXPECTED_THEMES:
        assert f'"{theme}"' in portal_js
