"""Versioned Phase 1 domain contracts.

These models are the typed boundary between later deterministic pipeline stages.
They do not perform network access, persistence, enrichment, or scoring.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PositiveInt,
    TypeAdapter,
    field_validator,
    model_validator,
)

SchemaVersion = Literal["1.0"]
type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
SHA256Hash = Annotated[str, BeforeValidator(lambda value: normalize_hash(value, 64))]
MD5Hash = Annotated[str, BeforeValidator(lambda value: normalize_hash(value, 32))]
SHA1Hash = Annotated[str, BeforeValidator(lambda value: normalize_hash(value, 40))]
UTCDateTime = Annotated[datetime, AfterValidator(lambda value: normalize_utc(value))]


class SourceType(StrEnum):
    """Supported Phase 1 source adapter families."""

    RSS = "rss"
    ATOM = "atom"
    JSON = "json"


class SourceCategory(StrEnum):
    """Controlled source precedence categories."""

    VULNERABILITIES = "vulnerabilities"
    CERT_ADVISORIES = "cert_advisories"
    THREAT_RESEARCH = "threat_research"
    INCIDENT_RESPONSE = "incident_response"
    VENDOR_ADVISORIES = "vendor_advisories"
    NEWS = "news"


class ReliabilityClassification(StrEnum):
    """Evidence-quality classification for a configured public source."""

    AUTHORITATIVE = "authoritative"
    PRIMARY_RESEARCH = "primary_research"
    INCIDENT_RESPONSE = "incident_response"
    GENERAL_NEWS = "general_news"


class IndicatorType(StrEnum):
    """Supported normalized indicator kinds."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    CVE = "cve"
    REGISTRY_PATH = "registry_path"
    FILE_PATH = "file_path"


class IndicatorValidationState(StrEnum):
    """Deterministic validation state for an indicator."""

    VALIDATED = "validated"
    INVALID = "invalid"
    SUPPRESSED = "suppressed"


class Severity(StrEnum):
    """Analyst severity, intentionally separate from confidence."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(StrEnum):
    """Normalized public-source document families."""

    ARTICLE = "article"
    ADVISORY = "advisory"
    BULLETIN = "bulletin"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    """Stable entity families used by relationship contracts."""

    INDICATOR = "indicator"
    VULNERABILITY = "vulnerability"
    PRODUCT = "product"
    ACTOR = "actor"
    MALWARE = "malware"
    CAMPAIGN = "campaign"
    INFRASTRUCTURE = "infrastructure"
    TECHNIQUE = "technique"
    REPORT = "report"


class EnrichmentStatus(StrEnum):
    """Provider and aggregate enrichment states without implying a risk score."""

    SUCCESS = "success"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    FAILED = "failed"
    DISABLED = "disabled"


class RelationshipOrigin(StrEnum):
    """How a relationship was created."""

    DETERMINISTIC = "deterministic"
    SOURCED_ASSERTION = "sourced_assertion"
    MODEL_INFERENCE = "model_inference"


class ReviewState(StrEnum):
    """Review state for non-source relationship or report content."""

    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class ReportState(StrEnum):
    """Report publication lifecycle."""

    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class DetectionType(StrEnum):
    """Detection artifact formats supported by later phases."""

    SIGMA = "sigma"
    YARA = "yara"
    SPL = "spl"
    KQL = "kql"


class RunStatus(StrEnum):
    """Ingestion and source-run lifecycle state."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class OperationalSeverity(StrEnum):
    """Severity for private operational events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CacheState(StrEnum):
    """Conditional-fetch/cache outcome for source runs."""

    MISS = "miss"
    HIT = "hit"
    NOT_MODIFIED = "not_modified"
    NOT_APPLICABLE = "not_applicable"


class ContractModel(BaseModel):
    """Common strict, immutable, versioned contract behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    schema_version: SchemaVersion = Field(
        default="1.0", description="Version of this externally exchanged contract."
    )

    def stable_json(self) -> str:
        """Serialize deterministically while omitting unset optional fields."""

        return self.model_dump_json(exclude_none=True, by_alias=True)


def normalize_utc(value: datetime) -> datetime:
    """Require timezone-aware timestamps and normalize them to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def normalize_cve_id(value: str) -> str:
    """Normalize and validate a CVE identifier without external lookups."""

    normalized = value.strip().upper()
    if not re.fullmatch(r"CVE-\d{4}-\d{4,}", normalized):
        raise ValueError("must match CVE-YYYY-NNNN")
    return normalized


def normalize_hash(value: str, expected_length: int) -> str:
    """Normalize a hexadecimal hash and enforce its algorithm length."""

    normalized = value.strip().lower()
    if len(normalized) != expected_length or not re.fullmatch(r"[0-9a-f]+", normalized):
        raise ValueError(f"must be {expected_length} hexadecimal characters")
    return normalized


def normalize_domain(value: str) -> str:
    """Normalize a DNS name without performing DNS resolution."""

    normalized = value.strip().lower().rstrip(".")
    if len(normalized) > 253 or not re.fullmatch(
        r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
        normalized,
    ):
        raise ValueError("must be a valid fully qualified domain name")
    return normalized


def normalize_attack_id(value: str) -> str:
    """Normalize a MITRE ATT&CK technique identifier."""

    normalized = value.strip().upper()
    if not re.fullmatch(r"T\d{4}(?:\.\d{3})?", normalized):
        raise ValueError("must match ATT&CK technique form T1234 or T1234.001")
    return normalized


def validate_http_url(value: AnyHttpUrl) -> AnyHttpUrl:
    """Validate an HTTP(S) URL and reject embedded credentials."""

    parsed = urlsplit(str(value))
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not contain credentials")
    return value


def normalize_http_url(value: AnyHttpUrl) -> str:
    """Return the validated HTTP(S) URL as a stable string."""

    return str(validate_http_url(value))


def sha256_text(value: str) -> str:
    """Return a deterministic SHA-256 digest for textual contract content."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


HttpURL = Annotated[AnyHttpUrl, AfterValidator(validate_http_url)]
CVEId = Annotated[str, BeforeValidator(normalize_cve_id)]
AttackId = Annotated[str, BeforeValidator(normalize_attack_id)]


class SourceConfig(ContractModel):
    """Private source registry entry accepted from the legacy JSON shape."""

    source_id: str = Field(
        default="", description="Stable slug used for deduplication and provenance."
    )
    name: str = Field(..., min_length=1, max_length=200, description="Display name.")
    source_type: SourceType = Field(
        ..., validation_alias="type", description="Configured adapter family."
    )
    url: HttpURL = Field(..., description="Canonical public source URL.")
    category: SourceCategory = Field(..., description="Controlled CTI category.")
    enabled: bool = Field(
        default=True, description="Whether future collection may use it."
    )
    polling_interval_seconds: PositiveInt = Field(
        default=86_400,
        ge=60,
        description="Minimum polling interval in seconds.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Per-request timeout budget in seconds.",
    )
    max_response_bytes: PositiveInt = Field(
        default=10_485_760,
        le=104_857_600,
        description="Maximum accepted response size in bytes.",
    )
    reliability: ReliabilityClassification = Field(
        default=ReliabilityClassification.GENERAL_NEWS,
        description="Evidence-quality classification.",
    )
    tags: tuple[str, ...] = Field(default=(), description="Stable source labels.")
    adapter_settings: dict[str, JSONValue] = Field(
        default_factory=dict,
        description="Non-secret adapter options; credentials are forbidden.",
    )

    @field_validator("tags")
    @classmethod
    def sort_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def derive_source_id(self) -> SourceConfig:
        if self.source_id:
            return self
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        object.__setattr__(self, "source_id", slug or "source")
        return self


class SourceRegistry(ContractModel):
    """Typed, deterministically ordered source configuration document."""

    sources: tuple[SourceConfig, ...] = Field(
        ..., min_length=1, description="Configured public CTI sources."
    )

    @model_validator(mode="after")
    def validate_unique_sources(self) -> SourceRegistry:
        source_ids = tuple(source.source_id for source in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        ordered = tuple(sorted(self.sources, key=lambda source: source.source_id))
        object.__setattr__(self, "sources", ordered)
        return self


class PublicSourceReference(ContractModel):
    """Safe source citation suitable for public report responses."""

    source_id: str = Field(..., description="Stable source identifier.")
    name: str = Field(..., description="Public source name.")
    canonical_url: HttpURL = Field(..., description="Public canonical source URL.")
    category: SourceCategory = Field(..., description="Public source category.")
    reliability: ReliabilityClassification = Field(
        ..., description="Public evidence-quality classification."
    )


class PersistenceSourceConfig(SourceConfig):
    """Database-facing source projection with operational history fields."""

    configuration_version: int = Field(
        default=1, ge=1, description="Version of the stored source configuration."
    )
    created_at: UTCDateTime | None = Field(
        default=None, description="UTC creation timestamp."
    )
    updated_at: UTCDateTime | None = Field(
        default=None, description="UTC update timestamp."
    )
    last_successful_retrieval: UTCDateTime | None = Field(
        default=None, description="UTC timestamp of the last successful retrieval."
    )
    consecutive_failure_count: int = Field(
        default=0, ge=0, description="Current consecutive failure count."
    )


class RawArtifactMetadata(ContractModel):
    """Immutable raw-response metadata retained for provenance and deduplication."""

    raw_artifact_id: UUID = Field(..., description="Stable raw-artifact identifier.")
    source_id: str = Field(..., description="Source registry identifier.")
    retrieval_url: HttpURL = Field(..., description="URL used for retrieval.")
    canonical_url: HttpURL = Field(..., description="Canonical URL for deduplication.")
    retrieved_at: UTCDateTime = Field(..., description="UTC retrieval timestamp.")
    response_status: int = Field(..., ge=100, le=599, description="HTTP status code.")
    content_type: str | None = Field(default=None, description="Response media type.")
    encoding: str | None = Field(
        default=None, description="Response character encoding."
    )
    etag: str | None = Field(default=None, description="HTTP ETag value.")
    last_modified: str | None = Field(
        default=None, description="HTTP Last-Modified value."
    )
    content_hash: SHA256Hash = Field(..., description="SHA-256 response content hash.")
    byte_length: int = Field(..., ge=0, description="Raw response length in bytes.")
    storage_locator: str | None = Field(
        default=None, description="Private immutable storage locator."
    )
    ingestion_run_id: UUID = Field(..., description="Owning ingestion run identifier.")


class SourceDocument(ContractModel):
    """Normalized source evidence with immutable raw-artifact provenance."""

    source_document_id: UUID = Field(
        ..., description="Stable source-document identifier."
    )
    source_id: str = Field(..., description="Source registry identifier.")
    raw_artifact_id: UUID = Field(..., description="Immutable raw-artifact identifier.")
    external_source_id: str | None = Field(
        default=None, description="Source-provided stable item identifier."
    )
    canonical_url: HttpURL = Field(..., description="Canonical public document URL.")
    title: str = Field(..., min_length=1, description="Normalized document title.")
    authors: tuple[str, ...] = Field(default=(), description="Normalized authors.")
    published_at: UTCDateTime | None = Field(
        default=None, description="UTC source publication timestamp."
    )
    updated_at_source: UTCDateTime | None = Field(
        default=None, description="UTC source update timestamp."
    )
    retrieved_at: UTCDateTime = Field(..., description="UTC retrieval timestamp.")
    content_type: str = Field(
        default="text/plain", description="Retrieved source media type."
    )
    normalized_text: str = Field(..., description="Normalized text, not raw HTML.")
    sanitized_summary: str | None = Field(
        default=None, description="Sanitized source summary."
    )
    language: str | None = Field(
        default=None, description="BCP-47 language tag if known."
    )
    document_type: DocumentType = Field(..., description="Normalized document family.")
    normalized_content_hash: SHA256Hash = Field(
        ..., description="SHA-256 hash of normalized content."
    )
    supersedes_id: UUID | None = Field(
        default=None, description="Prior source-document version, if any."
    )
    parse_version: str = Field(
        ..., min_length=1, description="Parser contract version."
    )


class ArticleAdvisory(SourceDocument):
    """Source-document specialization for article or advisory records."""

    publisher: str | None = Field(
        default=None, description="Publisher name if supplied."
    )


class Indicator(ContractModel):
    """Validated internal indicator with deterministic normalized value."""

    indicator_id: UUID = Field(..., description="Stable indicator identifier.")
    indicator_type: IndicatorType = Field(..., description="Indicator kind.")
    value: str = Field(..., min_length=1, description="Canonical indicator value.")
    normalized_value: str | None = Field(
        default=None, description="Deterministic lookup value."
    )
    safe_display_value: str | None = Field(
        default=None, description="Safe display value for a public projection."
    )
    validation_state: IndicatorValidationState = Field(
        default=IndicatorValidationState.VALIDATED,
        description="Deterministic validation state.",
    )
    first_seen_at: UTCDateTime | None = Field(
        default=None, description="UTC first-observed timestamp."
    )
    last_seen_at: UTCDateTime | None = Field(
        default=None, description="UTC last-observed timestamp."
    )
    source_document_ids: tuple[UUID, ...] = Field(
        default=(), description="Evidence source-document identifiers."
    )
    suppression_reason: str | None = Field(
        default=None, description="Private suppression explanation."
    )

    @model_validator(mode="after")
    def validate_and_normalize(self) -> Indicator:
        normalized = normalize_indicator_value(self.indicator_type, self.value)
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "normalized_value", normalized)
        if self.safe_display_value is None:
            object.__setattr__(self, "safe_display_value", normalized)
        return self


class PublicIndicator(ContractModel):
    """Public indicator projection that intentionally excludes raw value fields."""

    indicator_id: UUID = Field(..., description="Stable public indicator identifier.")
    indicator_type: IndicatorType = Field(..., description="Indicator kind.")
    safe_display_value: str = Field(..., description="Safe display representation.")
    validation_state: IndicatorValidationState = Field(
        ..., description="Validation disposition safe for publication."
    )
    first_seen_at: UTCDateTime | None = Field(
        default=None, description="UTC first-observed timestamp."
    )
    last_seen_at: UTCDateTime | None = Field(
        default=None, description="UTC last-observed timestamp."
    )


class PersistenceIndicator(Indicator):
    """Persistence projection with lifecycle metadata not exposed publicly."""

    record_status: str = Field(
        default="active", description="Persistence lifecycle state."
    )
    created_at: UTCDateTime | None = Field(
        default=None, description="UTC creation time."
    )
    updated_at: UTCDateTime | None = Field(default=None, description="UTC update time.")
    created_by_origin: str = Field(
        default="deterministic", description="Origin of the stored record."
    )
    deleted_at: UTCDateTime | None = Field(
        default=None, description="UTC soft-delete time."
    )


def normalize_indicator_value(indicator_type: IndicatorType, value: str) -> str:
    """Normalize and validate an indicator without network or filesystem access."""

    candidate = value.strip()
    if indicator_type is IndicatorType.IPV4:
        address = ipaddress.ip_address(candidate)
        if address.version != 4:
            raise ValueError("must be an IPv4 address")
        return str(address)
    if indicator_type is IndicatorType.IPV6:
        address = ipaddress.ip_address(candidate)
        if address.version != 6:
            raise ValueError("must be an IPv6 address")
        return str(address)
    if indicator_type is IndicatorType.DOMAIN:
        return normalize_domain(candidate)
    if indicator_type is IndicatorType.URL:
        return normalize_http_url(TypeAdapter(AnyHttpUrl).validate_python(candidate))
    if indicator_type is IndicatorType.EMAIL:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", candidate):
            raise ValueError("must be a valid email-like indicator")
        return candidate.lower()
    if indicator_type is IndicatorType.MD5:
        return normalize_hash(candidate, 32)
    if indicator_type is IndicatorType.SHA1:
        return normalize_hash(candidate, 40)
    if indicator_type is IndicatorType.SHA256:
        return normalize_hash(candidate, 64)
    if indicator_type is IndicatorType.CVE:
        return normalize_cve_id(candidate)
    if indicator_type in {IndicatorType.FILE_PATH, IndicatorType.REGISTRY_PATH}:
        if not candidate or "\x00" in candidate:
            raise ValueError("path indicator must be non-empty and NUL-free")
        return candidate
    raise ValueError("unsupported indicator type")


class IndicatorEvidence(ContractModel):
    """Evidence span linking an indicator to immutable source text."""

    evidence_id: UUID = Field(..., description="Stable evidence identifier.")
    source_document_id: UUID = Field(..., description="Source-document identifier.")
    indicator_id: UUID = Field(..., description="Indicator identifier.")
    start_offset: int = Field(..., ge=0, description="Inclusive text offset.")
    end_offset: int = Field(..., ge=1, description="Exclusive text offset.")
    evidence_text: str = Field(..., min_length=1, description="Captured evidence span.")
    context: str | None = Field(
        default=None, description="Optional surrounding context."
    )
    confidence: Confidence = Field(
        ..., description="Evidence confidence from zero to one."
    )

    @model_validator(mode="after")
    def validate_span(self) -> IndicatorEvidence:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class Vulnerability(ContractModel):
    """CVE contract containing evidence-backed attributes without scoring logic."""

    vulnerability_id: UUID = Field(..., description="Stable vulnerability identifier.")
    cve_id: CVEId = Field(..., description="Normalized CVE identifier.")
    description: str | None = Field(
        default=None, description="Public vulnerability summary."
    )
    published_at: UTCDateTime | None = Field(
        default=None, description="UTC publication time."
    )
    modified_at: UTCDateTime | None = Field(
        default=None, description="UTC modified time."
    )
    cvss_score: float | None = Field(
        default=None, ge=0, le=10, description="CVSS score."
    )
    epss_score: Confidence | None = Field(default=None, description="EPSS probability.")
    known_exploited: bool | None = Field(
        default=None, description="Known-exploitation state when evidenced."
    )
    cwe_ids: tuple[str, ...] = Field(default=(), description="CWE identifiers.")
    severity: Severity | None = Field(
        default=None, description="Analyst severity, not score."
    )
    confidence: Confidence = Field(default=0.0, description="Evidence confidence.")
    source_document_ids: tuple[UUID, ...] = Field(
        default=(), description="Supporting source-document identifiers."
    )


class Product(ContractModel):
    """Normalized vendor/product identity used by affected-product contracts."""

    product_id: UUID = Field(..., description="Stable product identifier.")
    vendor: str = Field(..., min_length=1, description="Display vendor name.")
    product: str = Field(..., min_length=1, description="Display product name.")
    normalized_vendor: str | None = Field(
        default=None, description="Normalized vendor key."
    )
    normalized_product: str | None = Field(
        default=None, description="Normalized product key."
    )
    ecosystem: str | None = Field(default=None, description="Product ecosystem.")
    product_type: str | None = Field(default=None, description="Product type.")
    canonical_identifiers: tuple[str, ...] = Field(
        default=(), description="CPE or other canonical product identifiers."
    )

    @model_validator(mode="after")
    def normalize_identity(self) -> Product:
        if self.normalized_vendor is None:
            object.__setattr__(self, "normalized_vendor", self.vendor.casefold())
        if self.normalized_product is None:
            object.__setattr__(self, "normalized_product", self.product.casefold())
        return self


class AffectedProduct(ContractModel):
    """Evidence-backed relationship between a vulnerability and product."""

    affected_product_id: UUID = Field(
        ..., description="Stable affected-product identifier."
    )
    vulnerability_id: UUID = Field(..., description="Vulnerability identifier.")
    product: Product = Field(..., description="Normalized affected product.")
    version_range: str | None = Field(
        default=None, description="Affected version range."
    )
    cpe: str | None = Field(default=None, description="CPE identifier if sourced.")
    affected_status: str = Field(
        ..., min_length=1, description="Affected status from evidence."
    )
    source_claim: str | None = Field(
        default=None, description="Supporting source claim."
    )
    confidence: Confidence = Field(..., description="Relationship confidence.")
    remediation_available: bool | None = Field(
        default=None, description="Whether remediation is evidenced as available."
    )


class AttackTechniqueMapping(ContractModel):
    """ATT&CK technique mapping with source confidence and provenance."""

    mapping_id: UUID = Field(..., description="Stable ATT&CK mapping identifier.")
    attack_id: AttackId = Field(..., description="ATT&CK technique identifier.")
    name: str = Field(..., min_length=1, description="Technique name.")
    tactic: str | None = Field(default=None, description="ATT&CK tactic.")
    platforms: tuple[str, ...] = Field(default=(), description="Applicable platforms.")
    framework_version: str = Field(..., min_length=1, description="ATT&CK version.")
    description_reference: HttpURL | None = Field(
        default=None, description="Public ATT&CK reference URL."
    )
    confidence: Confidence = Field(..., description="Mapping confidence.")
    source_document_ids: tuple[UUID, ...] = Field(
        default=(), description="Supporting source-document identifiers."
    )


class ProviderErrorClassification(StrEnum):
    """Stable, secret-free classifications for provider failures."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    RETRYABLE_HTTP = "retryable_http"
    HTTP_ERROR = "http_error"
    AUTHENTICATION = "authentication"
    MALFORMED_PAYLOAD = "malformed_payload"
    SCHEMA_DRIFT = "schema_drift"
    INVALID_REQUEST = "invalid_request"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class EntityReference(ContractModel):
    """Typed reference to a stable domain entity."""

    entity_type: EntityType = Field(..., description="Entity family.")
    entity_id: UUID = Field(..., description="Stable entity identifier.")


class ProviderRequest(ContractModel):
    """Bounded provider query with no credential-bearing fields."""

    entity: EntityReference = Field(..., description="Entity being enriched.")
    query_key: str = Field(..., min_length=1, max_length=512)
    query_kind: str = Field(default="cve", min_length=1, max_length=64)
    requested_at: UTCDateTime = Field(..., description="UTC request time.")


class ProviderRawMetadata(ContractModel):
    """Safe transport and quota metadata; response bodies are never logged here."""

    http_status: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = Field(default=None, max_length=255)
    response_bytes: int | None = Field(default=None, ge=0)
    etag: str | None = Field(default=None, max_length=512)
    last_modified: str | None = Field(default=None, max_length=255)
    retry_after_seconds: float | None = Field(default=None, ge=0)
    quota_remaining: int | None = Field(default=None, ge=0)
    quota_reset_at: UTCDateTime | None = None


class ProviderResponse(ContractModel):
    """Normalized provider response with immutable payload identity."""

    provider: str = Field(..., min_length=1, max_length=128)
    request: ProviderRequest = Field(..., description="Original typed request.")
    retrieved_at: UTCDateTime = Field(..., description="UTC retrieval time.")
    expires_at: UTCDateTime | None = Field(default=None)
    status: EnrichmentStatus = Field(...)
    retryable: bool = Field(default=False)
    normalized_result: dict[str, JSONValue] = Field(default_factory=dict)
    raw_metadata: ProviderRawMetadata = Field(default_factory=ProviderRawMetadata)
    payload_hash: SHA256Hash | None = Field(default=None)
    error_classification: ProviderErrorClassification | None = None
    error_detail: str | None = Field(default=None, max_length=255)
    cache_hit: bool = False


class ProviderHealth(ContractModel):
    """Private, secret-free provider health and quota snapshot."""

    provider: str = Field(..., min_length=1)
    enabled: bool
    state: EnrichmentStatus
    last_attempt_at: UTCDateTime | None = None
    last_success_at: UTCDateTime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    rate_limited_until: UTCDateTime | None = None
    quota_remaining: int | None = Field(default=None, ge=0)
    last_error_classification: ProviderErrorClassification | None = None


class ScoreComponent(ContractModel):
    """One auditable, bounded contribution to a priority score."""

    name: str = Field(..., min_length=1)
    value: float = Field(..., ge=0)
    maximum: float = Field(..., gt=0)
    rationale: str = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = ()


class PriorityScore(ContractModel):
    """Reproducible priority score kept separate from severity and confidence."""

    score_version: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=100)
    severity: Severity
    confidence: Confidence
    components: tuple[ScoreComponent, ...] = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def reproduce_score(self) -> PriorityScore:
        total = round(sum(component.value for component in self.components), 4)
        if round(self.score, 4) != total:
            raise ValueError("score must equal the sum of component values")
        if any(component.value > component.maximum for component in self.components):
            raise ValueError("component value cannot exceed its maximum")
        return self


class EnrichmentRunResult(ContractModel):
    """Aggregate provider results and score for one enrichment request."""

    entity: EntityReference
    status: EnrichmentStatus
    provider_results: tuple[ProviderResponse, ...] = ()
    normalized_result: dict[str, JSONValue] = Field(default_factory=dict)
    conflicts: dict[str, tuple[JSONValue, ...]] = Field(default_factory=dict)
    priority: PriorityScore | None = None


class EnrichmentResult(ContractModel):
    """Persistable provider result envelope with typed status and opaque payload."""

    enrichment_id: UUID = Field(..., description="Stable enrichment result identifier.")
    entity: EntityReference = Field(..., description="Enriched entity reference.")
    provider: str = Field(..., min_length=1, description="Provider name.")
    provider_query_key: str = Field(
        ..., min_length=1, description="Stable provider query key."
    )
    retrieved_at: UTCDateTime = Field(..., description="UTC provider retrieval time.")
    expires_at: UTCDateTime | None = Field(
        default=None, description="UTC cache expiry time."
    )
    status: EnrichmentStatus = Field(..., description="Provider result status.")
    normalized_result: dict[str, JSONValue] = Field(
        default_factory=dict, description="Provider-neutral normalized result."
    )
    raw_metadata: dict[str, JSONValue] = Field(
        default_factory=dict, description="Safe response and quota metadata."
    )
    raw_payload_hash: SHA256Hash | None = Field(
        default=None, description="Hash of retained provider payload."
    )
    cache_hit: bool = Field(
        default=False, description="Whether this result came from cache."
    )
    error_classification: str | None = Field(
        default=None, description="Safe retry/error classification."
    )
    quota_metadata: dict[str, JSONValue] | None = Field(
        default=None, description="Non-secret provider quota metadata."
    )


class RelationshipProposal(ContractModel):
    """Auditable relationship proposal separated from sourced fact."""

    proposal_id: UUID = Field(
        ..., description="Stable relationship proposal identifier."
    )
    source: EntityReference = Field(..., description="Source entity.")
    relationship_type: str = Field(
        ..., min_length=1, description="Relationship predicate."
    )
    target: EntityReference = Field(..., description="Target entity.")
    origin: RelationshipOrigin = Field(..., description="Relationship origin.")
    confidence: Confidence = Field(..., description="Relationship confidence.")
    justification: str = Field(
        ..., min_length=1, description="Evidence-linked justification."
    )
    review_state: ReviewState = Field(..., description="Review state.")
    evidence_ids: tuple[UUID, ...] = Field(
        default=(), description="Supporting evidence IDs."
    )
    prompt_version: str | None = Field(
        default=None, description="Model prompt version."
    )
    model_identifier: str | None = Field(default=None, description="Model identifier.")
    deterministic_rule: str | None = Field(
        default=None, description="Matching rule for deterministic relationships."
    )
    attribution_evidence_quality: (
        Literal["explicit_source", "corroborated_sources"] | None
    ) = Field(
        default=None,
        description="Evidence quality gate for actor attribution proposals.",
    )

    @model_validator(mode="after")
    def validate_origin_requirements(self) -> RelationshipProposal:
        if (
            self.origin is RelationshipOrigin.MODEL_INFERENCE
            and self.review_state
            not in {
                ReviewState.PROPOSED,
                ReviewState.REVIEWED,
            }
        ):
            raise ValueError(
                "model-inference relationships must be proposed or reviewed"
            )
        if (
            self.origin is RelationshipOrigin.SOURCED_ASSERTION
            and not self.evidence_ids
        ):
            raise ValueError("sourced assertions require evidence_ids")
        if (
            self.origin is RelationshipOrigin.DETERMINISTIC
            and not self.deterministic_rule
        ):
            raise ValueError("deterministic relationships require deterministic_rule")
        is_actor_attribution = self.target.entity_type is EntityType.ACTOR and any(
            token in self.relationship_type.casefold()
            for token in ("attribut", "actor")
        )
        if is_actor_attribution and (
            not self.evidence_ids or self.attribution_evidence_quality is None
        ):
            raise ValueError(
                "actor attribution requires explicit or corroborated source evidence"
            )
        return self


class ReportSummary(ContractModel):
    """Internal report summary with private provenance and caveat fields."""

    report_id: UUID = Field(..., description="Stable report identifier.")
    public_id: str = Field(
        ..., min_length=1, description="Non-sequential public identifier."
    )
    slug: str = Field(..., min_length=1, description="Stable canonical report slug.")
    headline: str = Field(
        ..., min_length=1, description="Evidence-constrained headline."
    )
    report_type: str = Field(..., min_length=1, description="Report purpose/type.")
    severity: Severity = Field(..., description="Analyst severity.")
    confidence: Confidence = Field(..., description="Analytical confidence.")
    state: ReportState = Field(..., description="Publication state.")
    first_published_at: UTCDateTime | None = Field(
        default=None, description="UTC first-publication timestamp."
    )
    last_updated_at: UTCDateTime = Field(
        ..., description="UTC latest update timestamp."
    )
    current_version: int = Field(
        ..., ge=1, description="Current report version number."
    )
    resurfaced: bool = Field(
        default=False, description="Whether new evidence resurfaced it."
    )
    primary_entities: tuple[EntityReference, ...] = Field(
        default=(), description="Primary related entities."
    )
    source_document_ids: tuple[UUID, ...] = Field(
        default=(), description="Private source-document provenance."
    )
    analytical_caveats: tuple[str, ...] = Field(
        default=(), description="Private analytical caveats."
    )


class PublicReportSummary(ContractModel):
    """Public report projection excluding private evidence IDs and caveats."""

    public_id: str = Field(..., description="Public report identifier.")
    slug: str = Field(..., description="Canonical report slug.")
    headline: str = Field(..., description="Public evidence-constrained headline.")
    severity: Severity = Field(..., description="Public severity.")
    confidence: Confidence = Field(..., description="Public confidence.")
    state: ReportState = Field(..., description="Public publication state.")
    first_published_at: UTCDateTime | None = Field(
        default=None, description="UTC first-publication timestamp."
    )
    last_updated_at: UTCDateTime = Field(
        ..., description="UTC latest update timestamp."
    )
    resurfaced: bool = Field(
        default=False, description="Whether new evidence resurfaced it."
    )
    source_count: int = Field(default=0, ge=0, description="Independent source count.")
    hunt_available: bool = Field(
        default=False, description="Whether a hunt is available."
    )
    remediation_available: bool = Field(
        default=False, description="Whether remediation guidance is available."
    )


class ThreatHunt(ContractModel):
    """Separate threat-hunting guidance contract."""

    hunt_id: UUID = Field(..., description="Stable hunt identifier.")
    report_version_id: UUID = Field(
        ..., description="Owning report version identifier."
    )
    objective: str = Field(..., min_length=1, description="Hunt objective.")
    scope: str = Field(..., min_length=1, description="Hunt scope.")
    platforms: tuple[str, ...] = Field(default=(), description="Applicable platforms.")
    telemetry_requirements: tuple[str, ...] = Field(
        default=(), description="Required telemetry and data sources."
    )
    lookback: str = Field(..., min_length=1, description="Recommended time range.")
    hypothesis: str = Field(..., min_length=1, description="Hunt hypothesis.")
    procedure: tuple[str, ...] = Field(
        ..., min_length=1, description="Ordered hunt steps."
    )
    expected_evidence: tuple[str, ...] = Field(
        default=(), description="Expected evidence observations."
    )
    false_positives: tuple[str, ...] = Field(
        default=(), description="Benign explanations."
    )
    escalation_criteria: tuple[str, ...] = Field(
        default=(), description="Escalation criteria."
    )
    validation_checklist: tuple[str, ...] = Field(
        default=(), description="Validation checklist."
    )
    queries: tuple[str, ...] = Field(
        default=(), description="Optional hunt queries or query templates."
    )
    evidence_ids: tuple[UUID, ...] = Field(
        default=(), description="Evidence supporting the hunt hypothesis."
    )
    detection_ids: tuple[UUID, ...] = Field(
        default=(), description="Related detection IDs."
    )
    source_references: tuple[PublicSourceReference, ...] = Field(
        default=(), description="Public source references."
    )


class Remediation(ContractModel):
    """Separate remediation and recovery guidance contract."""

    remediation_id: UUID = Field(..., description="Stable remediation identifier.")
    report_version_id: UUID = Field(
        ..., description="Owning report version identifier."
    )
    immediate_containment: tuple[str, ...] = Field(
        default=(), description="Immediate containment actions."
    )
    exposure_reduction: tuple[str, ...] = Field(
        default=(), description="Exposure-reduction actions."
    )
    patching: tuple[str, ...] = Field(
        default=(), description="Patch or upgrade guidance."
    )
    configuration_changes: tuple[str, ...] = Field(
        default=(), description="Configuration changes."
    )
    credential_actions: tuple[str, ...] = Field(
        default=(), description="Credential or secret actions."
    )
    blocking_limitations: tuple[str, ...] = Field(
        default=(), description="IOC-blocking limitations."
    )
    evidence_preservation: tuple[str, ...] = Field(
        default=(), description="Evidence-preservation cautions."
    )
    recovery: tuple[str, ...] = Field(default=(), description="Recovery guidance.")
    verification: tuple[str, ...] = Field(default=(), description="Verification steps.")
    rollback: tuple[str, ...] = Field(
        default=(), description="Rollback considerations."
    )
    evidence_ids: tuple[UUID, ...] = Field(
        default=(), description="Evidence supporting remediation actions."
    )
    references: tuple[HttpURL, ...] = Field(
        default=(), description="Authoritative references."
    )
    state: ReportState = Field(
        default=ReportState.DRAFT, description="Remediation state."
    )


class DetectionArtifact(ContractModel):
    """Machine-readable detection artifact contract."""

    detection_id: UUID = Field(..., description="Stable detection identifier.")
    report_version_id: UUID = Field(
        ..., description="Owning report version identifier."
    )
    detection_type: DetectionType = Field(..., description="Detection format.")
    title: str = Field(..., min_length=1, description="Detection title.")
    content: str = Field(..., min_length=1, description="Detection source content.")
    telemetry_requirements: tuple[str, ...] = Field(
        default=(), description="Required telemetry."
    )
    assumptions: tuple[str, ...] = Field(
        default=(), description="Field/index assumptions."
    )
    attack_techniques: tuple[AttackId, ...] = Field(
        default=(), description="Referenced ATT&CK techniques."
    )
    evidence_ids: tuple[UUID, ...] = Field(
        default=(), description="Evidence supporting the artifact."
    )
    validation_tool: str | None = Field(
        default=None, description="Validation tool name."
    )
    validation_result: str | None = Field(
        default=None, description="Validation result summary."
    )
    artifact_hash: SHA256Hash | None = Field(
        default=None, description="SHA-256 hash of artifact content."
    )
    state: ReportState = Field(default=ReportState.DRAFT, description="Artifact state.")

    @model_validator(mode="after")
    def derive_artifact_hash(self) -> DetectionArtifact:
        if self.artifact_hash is None:
            object.__setattr__(self, "artifact_hash", sha256_text(self.content))
        return self


class SourceRunResult(ContractModel):
    """Private per-source outcome included in an ingestion run manifest."""

    source_id: str = Field(..., description="Source registry identifier.")
    started_at: UTCDateTime = Field(..., description="UTC source-run start time.")
    completed_at: UTCDateTime | None = Field(
        default=None, description="UTC source-run completion time."
    )
    status: RunStatus = Field(..., description="Source-run status.")
    http_status: int | None = Field(
        default=None, ge=100, le=599, description="HTTP status."
    )
    item_count: int = Field(default=0, ge=0, description="Normalized item count.")
    retry_count: int = Field(default=0, ge=0, description="Retry count.")
    cache_state: CacheState = Field(
        ..., description="Cache/conditional request outcome."
    )
    error_classification: str | None = Field(
        default=None, description="Safe error classification."
    )
    error_detail: str | None = Field(
        default=None, description="Private safe operational error detail."
    )


class PublicSourceRunResult(ContractModel):
    """Minimal public-safe source outcome without operational error details."""

    source_id: str = Field(..., description="Source registry identifier.")
    status: RunStatus = Field(..., description="Published source-run status.")
    item_count: int = Field(default=0, ge=0, description="Published item count.")


class IngestionRunManifest(ContractModel):
    """Private deterministic run manifest for future ingestion execution."""

    ingestion_run_id: UUID = Field(..., description="Stable ingestion run identifier.")
    run_type: str = Field(..., min_length=1, description="Run purpose/type.")
    idempotency_key: str = Field(..., min_length=1, description="Stable rerun key.")
    scheduled_for: UTCDateTime | None = Field(
        default=None, description="UTC scheduled execution time."
    )
    started_at: UTCDateTime | None = Field(default=None, description="UTC start time.")
    completed_at: UTCDateTime | None = Field(
        default=None, description="UTC completion time."
    )
    status: RunStatus = Field(..., description="Run status.")
    triggering_origin: str = Field(
        ..., min_length=1, description="Triggering service/profile."
    )
    application_version: str = Field(
        ..., min_length=1, description="Application version."
    )
    configuration_hash: SHA256Hash = Field(
        ..., description="Source configuration hash."
    )
    total_sources: int = Field(default=0, ge=0, description="Total configured sources.")
    successful_sources: int = Field(
        default=0, ge=0, description="Successful source count."
    )
    failed_sources: int = Field(default=0, ge=0, description="Failed source count.")
    new_documents: int = Field(default=0, ge=0, description="New document count.")
    changed_documents: int = Field(
        default=0, ge=0, description="Changed document count."
    )
    unchanged_documents: int = Field(
        default=0, ge=0, description="Unchanged document count."
    )
    source_results: tuple[SourceRunResult, ...] = Field(
        default=(), description="Deterministically ordered private source results."
    )
    error_summary: str | None = Field(
        default=None, description="Safe private error summary."
    )


class OperationalEvent(ContractModel):
    """Private machine-readable operational event."""

    event_id: UUID = Field(..., description="Stable operational event identifier.")
    event_type: str = Field(
        ..., min_length=1, description="Machine-readable event type."
    )
    severity: OperationalSeverity = Field(..., description="Operational severity.")
    component: str = Field(..., min_length=1, description="Emitting component.")
    run_id: UUID | None = Field(default=None, description="Related ingestion run ID.")
    occurred_at: UTCDateTime = Field(..., description="UTC event timestamp.")
    payload: dict[str, JSONValue] = Field(
        default_factory=dict, description="Non-secret structured event payload."
    )
    acknowledged: bool = Field(
        default=False, description="Whether operations acknowledged it."
    )
    public_safe: bool = Field(
        default=False, description="Explicit publication-safety classification."
    )
