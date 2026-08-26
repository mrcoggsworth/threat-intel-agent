"""Public entity and relationship projection contract tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.models.contracts import EntityType, RelationshipOrigin
from hermes_cti.portal.entity_contracts import (
    PublicEntity,
    PublicEntityReference,
    PublicRelationship,
    PublicRelationshipPage,
)
from hermes_cti.portal.service import PortalService


class MemoryEntityService(PortalService):
    async def get_public_entity(
        self, entity_type: str, identifier: str
    ) -> PublicEntity | None:
        if (
            entity_type != EntityType.VULNERABILITY.value
            or identifier != "CVE-2026-1234"
        ):
            return None
        return PublicEntity(
            entity_type=EntityType.VULNERABILITY,
            public_key="CVE-2026-1234",
            display_name="CVE-2026-1234",
        )

    async def public_relationships(
        self,
        *,
        entity_type: str | None = None,
        identifier: str | None = None,
        limit: int = 100,
    ) -> PublicRelationshipPage:
        if entity_type is not None and identifier != "CVE-2026-1234":
            return PublicRelationshipPage(items=(), limit=min(limit, 100))
        return PublicRelationshipPage(
            items=(
                PublicRelationship(
                    source=PublicEntityReference(
                        entity_type=EntityType.VULNERABILITY,
                        public_key="CVE-2026-1234",
                        display_name="CVE-2026-1234",
                    ),
                    relationship_type="affects",
                    target=PublicEntityReference(
                        entity_type=EntityType.PRODUCT,
                        public_key="vendor|product|unknown",
                        display_name="Vendor Product",
                    ),
                    direction="forward",
                    origin=RelationshipOrigin.DETERMINISTIC,
                    confidence=1.0,
                ),
            ),
            limit=min(limit, 100),
        )


def test_public_entity_projection_omits_internal_database_identifiers() -> None:
    service = MemoryEntityService()
    client = TestClient(
        create_app(
            settings=Settings(
                admin_token=SecretStr("test-admin"), database_required=False
            ),
            portal_service=service,
        )
    )
    response = client.get("/api/v1/public/entities/vulnerability/CVE-2026-1234")
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "entity_type": "vulnerability",
        "public_key": "CVE-2026-1234",
        "display_name": "CVE-2026-1234",
        "first_seen_at": None,
        "last_seen_at": None,
        "source_count": 0,
    }
    assert "entity_id" not in response.json()


def test_public_relationship_filter_requires_a_complete_pair() -> None:
    client = TestClient(
        create_app(
            settings=Settings(database_required=False),
            portal_service=MemoryEntityService(),
        )
    )
    response = client.get(
        "/api/v1/public/relationships",
        params={"entity_type": "vulnerability"},
    )
    assert response.status_code == 400


def test_public_relationship_projection_uses_public_endpoint_keys() -> None:
    client = TestClient(
        create_app(
            settings=Settings(database_required=False),
            portal_service=MemoryEntityService(),
        )
    )
    response = client.get(
        "/api/v1/public/relationships",
        params={
            "entity_type": "vulnerability",
            "identifier": "CVE-2026-1234",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["source"]["public_key"] == "CVE-2026-1234"
    assert "entity_id" not in body["items"][0]["source"]
