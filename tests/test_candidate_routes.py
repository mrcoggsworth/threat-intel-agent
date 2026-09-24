"""Route-level coverage for the analyst publication-candidate ledger API.

PUT /api/v1/analyst/candidates/{candidate_id} and
GET /api/v1/analyst/candidates are the authenticated boundary the daily
analyst profile uses to make publication progress durable. Fail-closed 404
auth is pinned by tests/test_analyst_api_routing.py; the functional ledger
repository behavior is pinned by tests/test_candidate_ledger.py.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import insert

from hermes_cti.analyst.candidate_ledger import candidate_identity
from hermes_cti.analyst.contracts import CandidateRecord
from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.db.models import IngestionRun

NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)
TOKEN_HEADERS = {"X-Analyst-Token": "test-analyst-token"}


def _build_client(postgres_settings: Settings) -> TestClient:
    settings = postgres_settings.model_copy(
        update={"analyst_token": SecretStr("test-analyst-token")}
    )
    return TestClient(create_app(settings=settings, portal_service=None))


def _record(run_id, event_identity: str = "cve:CVE-2026-76460", **overrides):
    payload = {
        "candidate_id": candidate_identity(run_id, event_identity),
        "run_id": run_id,
        "event_identity": event_identity,
        "event_type": "cve",
        "rank": 1,
        "lifecycle": "validated",
        "evidence_ids": [],
        "source_urls": ["https://example.test/advisory"],
    }
    payload.update(overrides)
    return CandidateRecord.model_validate(payload)


def test_put_candidate_persists_and_get_summarizes(postgres_settings) -> None:
    run_id = uuid4()

    async def seed() -> None:
        from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

        engine: AsyncEngine = create_async_engine(
            postgres_settings.database_url.get_secret_value()
        )
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    insert(IngestionRun).values(
                        id=run_id,
                        run_type="daily",
                        idempotency_key=f"routes:{run_id}",
                        status="completed",
                        triggering_origin="test",
                        application_version="test",
                        configuration_hash="0" * 64,
                        started_at=NOW,
                        completed_at=NOW,
                    )
                )
        finally:
            await engine.dispose()

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        pool.submit(lambda: asyncio.run(seed())).result()

    client = _build_client(postgres_settings)
    with client:
        record = _record(run_id)
        upserted = client.put(
            f"/api/v1/analyst/candidates/{record.candidate_id}",
            json=record.model_dump(mode="json"),
            headers=TOKEN_HEADERS,
        )
        assert upserted.status_code == 200, upserted.text

        # Natural-key idempotency: a second PUT updates the same candidate.
        updated = client.put(
            f"/api/v1/analyst/candidates/{record.candidate_id}",
            json=record.model_copy(
                update={"lifecycle": "published", "published_public_id": "PUB-2026-099"}
            ).model_dump(mode="json"),
            headers=TOKEN_HEADERS,
        )
        assert updated.status_code == 200

        summary = client.get(
            f"/api/v1/analyst/candidates?run_id={run_id}", headers=TOKEN_HEADERS
        )
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["total"] == 1
        assert payload["counts"]["published"] == 1
        assert payload["published_ids"] == ["PUB-2026-099"]

        # Candidate identity cannot be spoofed to another natural key.
        mismatch = client.put(
            f"/api/v1/analyst/candidates/{uuid4()}",
            json=record.model_dump(mode="json"),
            headers=TOKEN_HEADERS,
        )
        assert mismatch.status_code == 422

        # Unknown ingestion runs are rejected at the boundary.
        orphan = _record(uuid4())
        rejected = client.put(
            f"/api/v1/analyst/candidates/{orphan.candidate_id}",
            json=orphan.model_dump(mode="json"),
            headers=TOKEN_HEADERS,
        )
        assert rejected.status_code == 422
