"""Typed contracts for deterministic Phase 3 extraction."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from hermes_cti.models.contracts import (
    ContractModel,
    IndicatorType,
    IndicatorValidationState,
)


class IPExclusionClass(StrEnum):
    """Address classifications that are excluded from public IOC output."""

    PRIVATE = "private"
    LOOPBACK = "loopback"
    RESERVED = "reserved"
    MULTICAST = "multicast"
    DOCUMENTATION = "documentation"
    UNSPECIFIED = "unspecified"
    LINK_LOCAL = "link_local"


class ExtractionConfig(ContractModel):
    """Offline extraction policy and false-positive controls."""

    max_input_chars: int = Field(default=1_000_000, ge=1, le=10_000_000)
    context_chars: int = Field(default=80, ge=0, le=1_000)
    extract_email: bool = False
    extract_file_paths: bool = True
    extract_registry_paths: bool = True
    excluded_ip_classes: tuple[IPExclusionClass, ...] = (
        IPExclusionClass.PRIVATE,
        IPExclusionClass.LOOPBACK,
        IPExclusionClass.RESERVED,
        IPExclusionClass.MULTICAST,
        IPExclusionClass.DOCUMENTATION,
        IPExclusionClass.UNSPECIFIED,
        IPExclusionClass.LINK_LOCAL,
    )
    suppressed_domains: tuple[str, ...] = ()
    suppressed_values: tuple[str, ...] = ()

    @field_validator("excluded_ip_classes")
    @classmethod
    def stable_ip_classes(
        cls, value: tuple[IPExclusionClass, ...]
    ) -> tuple[IPExclusionClass, ...]:
        return tuple(dict.fromkeys(value))

    @field_validator("suppressed_domains")
    @classmethod
    def normalize_suppressed_domains(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted({item.strip().lower().rstrip(".") for item in value if item.strip()})
        )

    @field_validator("suppressed_values")
    @classmethod
    def normalize_suppressed_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({item.strip().lower() for item in value if item.strip()}))


class IndicatorObservation(ContractModel):
    """One validated indicator occurrence linked to source-document evidence."""

    observation_id: UUID = Field(..., description="Stable observation identifier.")
    indicator_type: IndicatorType
    original_display_value: str = Field(..., min_length=1)
    normalized_value: str = Field(..., min_length=1)
    source_document_id: UUID
    start_offset: int = Field(..., ge=0)
    end_offset: int = Field(..., ge=1)
    context: str = Field(default="")
    extraction_rule: str = Field(..., min_length=1)
    validation_state: IndicatorValidationState = IndicatorValidationState.VALIDATED
    suppression_reason: str | None = None

    @model_validator(mode="after")
    def validate_span(self) -> IndicatorObservation:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        if self.validation_state is IndicatorValidationState.SUPPRESSED:
            if not self.suppression_reason:
                raise ValueError("suppressed observations require a reason")
        elif self.suppression_reason is not None:
            raise ValueError("only suppressed observations may have a reason")
        return self

    @property
    def display_value(self) -> str:
        return self.original_display_value

    @property
    def evidence_text(self) -> str:
        return self.original_display_value

    @property
    def indicator_id(self) -> UUID:
        return self.observation_id


class CveCandidate(ContractModel):
    """A separately returned, normalized CVE candidate occurrence."""

    candidate_id: UUID
    original_display_value: str = Field(..., min_length=1)
    normalized_value: str = Field(..., pattern=r"^CVE-\d{4}-\d{4,}$")
    source_document_id: UUID
    start_offset: int = Field(..., ge=0)
    end_offset: int = Field(..., ge=1)
    context: str = Field(default="")
    extraction_rule: str = Field(..., min_length=1)
    validation_state: IndicatorValidationState = IndicatorValidationState.VALIDATED

    @model_validator(mode="after")
    def validate_span(self) -> CveCandidate:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        if self.validation_state is not IndicatorValidationState.VALIDATED:
            raise ValueError("CVE candidates must be validated")
        return self

    @property
    def display_value(self) -> str:
        return self.original_display_value

    @property
    def evidence_text(self) -> str:
        return self.original_display_value


class ExtractionResult(ContractModel):
    """Deterministically ordered extraction output for one source document."""

    source_document_id: UUID
    observations: tuple[IndicatorObservation, ...] = ()
    cve_candidates: tuple[CveCandidate, ...] = ()
    suppressed_observations: tuple[IndicatorObservation, ...] = ()

    @property
    def indicators(self) -> tuple[IndicatorObservation, ...]:
        return self.observations
