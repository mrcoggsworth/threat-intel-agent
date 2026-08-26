"""Offline checks for the Phase 9 data-model contract completion."""

import pytest
from sqlalchemy import CheckConstraint, Index

from hermes_cti.db.lifecycle import (
    LIFECYCLE_FIELDS,
    RECORD_STATUS_VALUES,
    validate_lifecycle_value,
)
from hermes_cti.db.models import Base


def test_normalized_entities_and_provenance_tables_are_registered() -> None:
    expected = {
        "threat_actor",
        "malware",
        "tool",
        "campaign",
        "infrastructure",
        "entity_evidence",
        "vulnerability_provider_observation",
        "vulnerability_attribute_selection",
        "source_configuration_history",
    }
    assert expected <= set(Base.metadata.tables)


def test_durable_tables_have_shared_audit_columns() -> None:
    for table in Base.metadata.tables.values():
        assert {"created_at", "updated_at", "record_status", "created_by_origin"} <= {
            column.name for column in table.columns
        }, table.name


def test_integrity_checks_and_query_indexes_are_declared() -> None:
    ingestion = Base.metadata.tables["ingestion_run"]
    assert "ck_ingestion_run_terminal_completion" in {
        constraint.name
        for constraint in ingestion.constraints
        if isinstance(constraint, CheckConstraint)
    }

    relationship = Base.metadata.tables["relationship"]
    assert {
        "ix_relationship_source",
        "ix_relationship_target",
    } <= {index.name for index in relationship.indexes if isinstance(index, Index)}

    evidence = Base.metadata.tables["entity_evidence"]
    assert "ck_entity_evidence_source" in {
        constraint.name
        for constraint in evidence.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_lifecycle_registry_covers_persisted_state_columns() -> None:
    expected = {
        ("ingestion_run", "status"),
        ("source_run", "status"),
        ("source_run", "cache_state"),
        ("indicator", "validation_state"),
        ("enrichment_result", "status"),
        ("risk_assessment", "review_state"),
        ("relationship", "review_state"),
        ("resurfacing_event", "review_state"),
        ("report", "state"),
        ("report_version", "validation_status"),
        ("hunt", "state"),
        ("remediation", "state"),
        ("detection", "state"),
        ("publication", "state"),
        ("model_run", "status"),
        ("threat_actor", "attribution_state"),
        ("campaign", "state"),
        ("infrastructure", "state"),
        ("affected_product", "affected_status"),
        ("vulnerability", "exploitation_state"),
        ("vulnerability_provider_observation", "status"),
        ("vulnerability_provider_observation", "exploitation_state"),
    }
    assert expected <= set(LIFECYCLE_FIELDS)
    assert RECORD_STATUS_VALUES == ("active", "superseded", "archived")
    assert all(values for values in LIFECYCLE_FIELDS.values())


def test_lifecycle_registry_rejects_unknown_values() -> None:
    for table, column in LIFECYCLE_FIELDS:
        with pytest.raises(ValueError, match=f"{table}\\.{column}"):
            validate_lifecycle_value(table, column, "__invalid_lifecycle_value__")


def test_vulnerability_contract_columns_are_typed_and_provenance_is_unique() -> None:
    vulnerability = Base.metadata.tables["vulnerability"]
    assert {
        "cvss_version",
        "cvss_vector",
        "epss_percentile",
        "epss_date",
        "cwe_ids",
        "kev_date_added",
        "kev_due_date",
        "exploitation_state",
    } <= {column.name for column in vulnerability.columns}
    raw_artifact = Base.metadata.tables["raw_artifact"]
    assert {
        "retention_policy",
        "retention_expires_at",
        "storage_state",
    } <= {column.name for column in raw_artifact.columns}
    history = Base.metadata.tables["source_configuration_history"]
    assert {
        "configuration_version",
        "configuration_hash",
        "configuration",
        "recorded_at",
    } <= {column.name for column in history.columns}
    selection = Base.metadata.tables["vulnerability_attribute_selection"]
    assert any(
        constraint.name == "uq_vulnerability_attribute_selection"
        for constraint in selection.constraints
    )
