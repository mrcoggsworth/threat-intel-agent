"""Central lifecycle registry shared by persistence metadata and migrations."""

from __future__ import annotations

import hashlib
from enum import StrEnum

from hermes_cti.models.contracts import (
    CacheState,
    EnrichmentStatus,
    ExploitationState,
    IndicatorValidationState,
    ReportState,
    ReviewState,
    RunStatus,
)


class RecordStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class PublicationState(StrEnum):
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ModelRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EntityState(StrEnum):
    UNKNOWN = "unknown"
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


class AttributionState(StrEnum):
    UNKNOWN = "unknown"
    SUSPECTED = "suspected"
    ATTRIBUTED = "attributed"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class AffectedStatus(StrEnum):
    AFFECTED = "affected"
    NOT_AFFECTED = "not_affected"
    UNKNOWN = "unknown"


def _values(enum: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum)


LIFECYCLE_FIELDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("ingestion_run", "status"): _values(RunStatus),
    ("source_run", "status"): _values(RunStatus),
    ("source_run", "cache_state"): _values(CacheState),
    ("indicator", "validation_state"): _values(IndicatorValidationState),
    ("enrichment_result", "status"): _values(EnrichmentStatus),
    ("vulnerability_provider_observation", "status"): _values(EnrichmentStatus),
    ("vulnerability", "exploitation_state"): _values(ExploitationState),
    ("vulnerability_provider_observation", "exploitation_state"): _values(
        ExploitationState
    ),
    ("risk_assessment", "review_state"): _values(ReviewState),
    ("relationship", "review_state"): _values(ReviewState),
    ("resurfacing_event", "review_state"): _values(ReviewState),
    ("report", "state"): _values(ReportState),
    ("report_version", "validation_status"): _values(ReportState),
    ("hunt", "state"): _values(ReportState),
    ("remediation", "state"): _values(ReportState),
    ("detection", "state"): _values(ReportState),
    ("publication", "state"): _values(PublicationState),
    ("model_run", "status"): _values(ModelRunStatus),
    ("threat_actor", "attribution_state"): _values(AttributionState),
    ("campaign", "state"): _values(EntityState),
    ("infrastructure", "state"): _values(EntityState),
    ("affected_product", "affected_status"): _values(AffectedStatus),
}

RECORD_STATUS_VALUES = _values(RecordStatus)


def constraint_name(table: str, column: str) -> str:
    value = f"ck_{table}_{column}_lifecycle"
    if len(value) <= 63:
        return value
    digest = hashlib.sha1(value.encode()).hexdigest()[:16]
    return f"ck_lifecycle_{digest}_lifecycle"


def validate_lifecycle_value(table: str, column: str, value: str) -> str:
    allowed = LIFECYCLE_FIELDS[(table, column)]
    if value not in allowed:
        raise ValueError(
            f"{table}.{column} must be one of {allowed}; received {value!r}"
        )
    return value
