"""Tests for interactive MITRE ATT&CK TTP modal endpoint and templates."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.models.contracts import AttackTechniqueMapping
from tests.test_phase8 import MemoryPortalService


def test_portal_attack_modal_endpoint_with_report_attack_mapping() -> None:
    portal_service = MemoryPortalService()
    mapping = AttackTechniqueMapping(
        mapping_id=uuid4(),
        attack_id="T1059.001",
        name="PowerShell",
        tactic="Execution",
        platforms=("Windows", "Linux", "macOS"),
        framework_version="v14.1",
        description_reference="https://attack.mitre.org/techniques/T1059/001/",
        confidence=0.9,
    )
    bundle = portal_service.bundle.model_copy(
        update={"attack_mappings": (mapping,)}
    )
    portal_service.bundle = bundle
    portal_service.version.structured_content = json.loads(bundle.stable_json())

    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/attack-modal?attack_id=T1059.001"
        )
        assert response.status_code == 200
        html = response.text
        assert "T1059.001" in html
        assert "MITRE ATT" in html
        assert "PowerShell" in html
        assert "Execution" in html
        assert "v14.1" in html
        assert "90% Confidence" in html
        assert "Windows" in html
        assert "https://attack.mitre.org/techniques/T1059/001/" in html
        assert portal_service.report.headline in html
        assert f"/reports/{portal_service.report.slug}" in html


def test_portal_attack_modal_standalone_fallback() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        # Standalone request for root technique
        response = client.get("/partials/attack-modal?attack_id=T1566")
        assert response.status_code == 200
        html = response.text
        assert "T1566" in html
        assert "MITRE ATT" in html
        assert "https://attack.mitre.org/techniques/T1566/" in html

        # Standalone request for sub-technique
        response_sub = client.get("/partials/attack-modal?attack_id=T1566.001")
        assert response_sub.status_code == 200
        assert "https://attack.mitre.org/techniques/T1566/001/" in response_sub.text


def test_techniques_fallback_page() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        response = client.get("/techniques/T1059.001")
        assert response.status_code == 200
        assert "Hermes CTI" in response.text


def test_portal_report_list_and_attack_section_triggers() -> None:
    portal_service = MemoryPortalService()
    mapping = AttackTechniqueMapping(
        mapping_id=uuid4(),
        attack_id="T1059.001",
        name="PowerShell",
        tactic="Execution",
        platforms=("Windows",),
        framework_version="v14.1",
        description_reference="https://attack.mitre.org/techniques/T1059/001/",
        confidence=0.9,
    )
    bundle = portal_service.bundle.model_copy(
        update={"attack_mappings": (mapping,)}
    )
    portal_service.bundle = bundle
    portal_service.version.structured_content = json.loads(bundle.stable_json())

    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        # Check report list partial contains modal triggers
        list_response = client.get("/partials/reports")
        assert list_response.status_code == 200
        assert "attack-modal?attack_id=T1059.001" in list_response.text

        # Check attack section partial contains modal triggers
        section_response = client.get(
            f"/partials/reports/{portal_service.report.slug}/section/attack"
        )
        assert section_response.status_code == 200
        assert "attack-modal?attack_id=T1059.001" in section_response.text
        assert "data-report-link" in section_response.text
