"""Contract and boundary tests for bounded analyst corpus queries."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import ValidationError

from hermes_cti.analyst.contracts import CorpusQuery, CorpusResource
from hermes_cti.analyst.corpus_repository import _decode_cursor, _encode_cursor
from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.models.contracts import EntityType, ReviewState


def test_corpus_query_is_bounded_and_rejects_partial_entity_filters() -> None:
    query = CorpusQuery(limit=100, cve_id="cve-2026-1")
    assert query.cve_id == "CVE-2026-1"

    try:
        CorpusQuery(limit=101)
    except ValidationError:
        pass
    else:
        raise AssertionError("limits above 100 must be rejected")

    try:
        CorpusQuery(entity_type=EntityType.ACTOR)
    except ValidationError:
        pass
    else:
        raise AssertionError("partial entity filters must be rejected")


def test_corpus_filters_are_resource_specific() -> None:
    query = CorpusQuery(review_state=ReviewState.REVIEWED)
    try:
        query.validate_for(CorpusResource.CVES)
    except ValueError as exc:
        assert "review_state" in str(exc)
    else:
        raise AssertionError("review filters must not apply to CVEs")


def test_corpus_cursor_round_trips_resource_and_keyset_values() -> None:
    row = type(
        "Row",
        (),
        {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "updated_at": datetime(2026, 9, 1, tzinfo=UTC),
        },
    )()
    cursor = _encode_cursor(CorpusResource.CVES, row)
    decoded = _decode_cursor(cursor, CorpusResource.CVES)
    assert decoded == (row.updated_at, row.id)

    try:
        _decode_cursor(cursor, CorpusResource.IOCS)
    except ValueError as exc:
        assert "invalid" in str(exc)
    else:
        raise AssertionError("a CVE cursor must not be accepted for IOC queries")


def test_corpus_route_is_private_and_rejects_unbounded_or_unsupported_queries() -> None:
    settings = Settings(
        analyst_token="test-analyst",
        database_required=False,
    )
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/v1/analyst/corpus/cves").status_code == 404
        assert (
            client.get(
                "/api/v1/analyst/corpus/cves",
                headers={"X-Analyst-Token": "test-analyst"},
            ).status_code
            == 503
        )
        assert (
            client.get(
                "/api/v1/analyst/corpus/cves",
                params={"limit": 101},
                headers={"X-Analyst-Token": "test-analyst"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/analyst/corpus/cves",
                params={"review_state": "reviewed"},
                headers={"X-Analyst-Token": "test-analyst"},
            ).status_code
            == 422
        )
        assert client.get("/api/v1/public/corpus/cves").status_code == 404
