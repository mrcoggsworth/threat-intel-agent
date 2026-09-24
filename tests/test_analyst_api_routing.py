"""Regression tests pinning the /api/v1/analyst router mount and fail-closed auth.

The analyst surface intentionally answers HTTP 404 to missing or mismatched
credentials (see require_analyst_token in src/hermes_cti/api/dependencies.py).
A 404 on /api/v1/analyst/* therefore signals an auth/secret problem, never a
missing route. These tests pin the mount contract so a future refactor cannot
silently drop the router or double-prefix it.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings

ANALYST_PREFIX = "/api/v1/analyst"

EXPECTED_ANALYST_PATHS = {
    "/api/v1/analyst/status",
    "/api/v1/analyst/runs/latest",
    "/api/v1/analyst/runs/{run_id}",
    "/api/v1/analyst/evidence",
    "/api/v1/analyst/proposals",
    "/api/v1/analyst/reports",
    "/api/v1/analyst/reports/validate",
    "/api/v1/analyst/corpus/{resource}",
    "/api/v1/analyst/candidates",
    "/api/v1/analyst/candidates/{candidate_id}",
}


def _build_app(settings: Settings) -> FastAPI:
    return create_app(settings=settings, portal_service=None)


def _token_only_settings() -> Settings:
    return Settings(analyst_token=SecretStr("test-analyst-token"), database_url=None)


def test_openapi_exposes_exactly_the_analyst_route_set() -> None:
    app = _build_app(_token_only_settings())
    paths = set(app.openapi()["paths"])

    registered = {path for path in paths if path.startswith(f"{ANALYST_PREFIX}/")}
    assert registered == EXPECTED_ANALYST_PATHS


def test_no_path_is_double_prefixed() -> None:
    app = _build_app(_token_only_settings())
    paths = set(app.openapi()["paths"])

    for path in paths:
        assert "/api/v1/analyst/api/v1/analyst" not in path, path
        assert not path.startswith("/api/v1/api/v1"), path


def test_analyst_status_fail_closed_auth_gate() -> None:
    with TestClient(_build_app(_token_only_settings())) as client:
        missing_token = client.get("/api/v1/analyst/status")
        wrong_token = client.get(
            "/api/v1/analyst/status", headers={"X-Analyst-Token": "wrong-token"}
        )
        authenticated = client.get(
            "/api/v1/analyst/status", headers={"X-Analyst-Token": "test-analyst-token"}
        )

    # Fail-closed: unauthenticated requests look like a missing route.
    assert missing_token.status_code == 404
    assert wrong_token.status_code == 404
    # A valid token passes the auth gate; the route resolves (200 with a
    # database, 503 when the database is not configured — never 404).
    assert authenticated.status_code in (200, 503)
