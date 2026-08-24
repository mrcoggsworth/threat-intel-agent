"""Typed detection-generation inputs and validation outputs for Phase 7."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from hermes_cti.models.contracts import ContractModel, SHA256Hash


class SigmaLogSource(ContractModel):
    """Sigma log-source declaration."""

    category: str | None = None
    product: str | None = None
    service: str | None = None


class SigmaFieldMatch(ContractModel):
    """One typed Sigma field/value comparison."""

    field: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=1, max_length=2048)
    modifier: Literal["equals", "contains", "startswith", "endswith"] = "equals"


class SigmaRuleSpec(ContractModel):
    """Minimal Sigma rule subset generated and parsed offline."""

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    logsource: SigmaLogSource
    matches: tuple[SigmaFieldMatch, ...] = Field(..., min_length=1)
    condition: str = Field(default="selection", min_length=1)
    level: Literal["informational", "low", "medium", "high", "critical"] = "medium"
    tags: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


class FileEvidence(ContractModel):
    """Public file evidence required before generating YARA."""

    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1)
    sha256: SHA256Hash | None = None
    strings: tuple[str, ...] = Field(..., min_length=1)
    public_source: str = Field(..., min_length=1)


class YaraRuleSpec(ContractModel):
    """Typed YARA source specification."""

    rule_name: str = Field(..., min_length=1, max_length=128)
    strings: tuple[str, ...] = Field(..., min_length=1)
    condition: str = Field(default="any of them", min_length=1)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_name(self) -> YaraRuleSpec:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.rule_name):
            raise ValueError("YARA rule_name must be an identifier")
        return self


class QuerySpec(ContractModel):
    """SPL/KQL query with explicit telemetry and platform assumptions."""

    backend: Literal["spl", "kql"]
    title: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)
    telemetry: tuple[str, ...] = Field(..., min_length=1)
    index: str | None = None
    fields: tuple[str, ...] = Field(..., min_length=1)
    conditions: tuple[SigmaFieldMatch, ...] = Field(..., min_length=1)
    template: bool = False
    evidence_ids: tuple[UUID, ...] = ()


class CompiledArtifact(ContractModel):
    """Result of external or deterministic compatibility validation."""

    valid: bool
    validator: str
    validation_result: str
    artifact_hash: SHA256Hash


class SigmaConversionResult(ContractModel):
    """Result of Sigma parsing and backend conversion."""

    parsed: SigmaRuleSpec
    converted: tuple[QuerySpec, ...]
    converter: str
    external_tool_used: bool
