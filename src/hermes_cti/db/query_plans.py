"""Representative PostgreSQL query-plan checks for deployment verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class QueryPlanCheck:
    """One bounded query and the index expected to support it."""

    name: str
    statement: str
    expected_indexes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryPlanResult:
    """The indexes and raw plan observed in one PostgreSQL EXPLAIN result."""

    name: str
    expected_indexes: tuple[str, ...]
    used_indexes: tuple[str, ...]
    plan: object

    @property
    def passed(self) -> bool:
        return bool(set(self.expected_indexes) & set(self.used_indexes))

    @property
    def has_sequential_scan(self) -> bool:
        """Return whether PostgreSQL selected a sequential scan in this plan."""

        return _contains_node_type(self.plan, "Seq Scan")


QUERY_PLAN_CHECKS: tuple[QueryPlanCheck, ...] = (
    QueryPlanCheck(
        "ingestion_schedule",
        """
        SELECT id FROM ingestion_run
        WHERE status IN ('scheduled', 'running')
          AND scheduled_for <= now()
        ORDER BY status, scheduled_for
        LIMIT 100
        """,
        ("ix_ingestion_run_status_schedule",),
    ),
    QueryPlanCheck(
        "source_document_identity",
        """
        SELECT id FROM source_document
        WHERE canonical_url = 'https://example.invalid/document'
          AND normalized_content_hash = repeat('a', 64)
        LIMIT 1
        """,
        ("ix_source_document_canonical_hash",),
    ),
    QueryPlanCheck(
        "relationship_source_endpoint",
        """
        SELECT id FROM relationship
        WHERE source_entity_type = 'actor'
          AND source_entity_id = '00000000-0000-0000-0000-000000000001'::uuid
          AND active = true
          AND review_state = 'reviewed'
        LIMIT 100
        """,
        ("ix_relationship_source",),
    ),
    QueryPlanCheck(
        "published_report_listing",
        """
        SELECT id FROM report
        WHERE state = 'published'
          AND last_updated_at >= now() - interval '90 days'
        ORDER BY last_updated_at DESC, id
        LIMIT 100
        """,
        ("ix_report_state_updated",),
    ),
    QueryPlanCheck(
        "published_entity_membership",
        """
        SELECT report_version_id FROM report_entity
        WHERE entity_type = 'actor'
          AND entity_id = '00000000-0000-0000-0000-000000000001'::uuid
        LIMIT 100
        """,
        ("ix_report_entity_entity",),
    ),
    QueryPlanCheck(
        "entity_evidence_lookup",
        """
        SELECT id FROM entity_evidence
        WHERE entity_type = 'actor'
          AND entity_id = '00000000-0000-0000-0000-000000000001'::uuid
        LIMIT 100
        """,
        ("ix_entity_evidence_entity",),
    ),
    QueryPlanCheck(
        "vulnerability_lookup",
        """
        SELECT id FROM vulnerability WHERE cve_id = 'CVE-2026-0001' LIMIT 1
        """,
        ("ix_vulnerability_cve", "uq_vulnerability_cve"),
    ),
    QueryPlanCheck(
        "product_lookup",
        """
        SELECT id FROM product
        WHERE normalized_vendor = 'example'
          AND normalized_product = 'product'
        LIMIT 1
        """,
        ("ix_product_vendor_name", "uq_product_natural_key"),
    ),
    QueryPlanCheck(
        "attack_technique_lookup",
        """
        SELECT id FROM attack_technique
        WHERE attack_id = 'T1059'
          AND framework_version = 'enterprise-v1'
        LIMIT 1
        """,
        ("ix_attack_technique_id", "uq_attack_technique_natural_key"),
    ),
    QueryPlanCheck(
        "published_report_full_text",
        """
        SELECT id FROM report_version
        WHERE to_tsvector(
            'simple',
            coalesce(executive_summary, '') || ' ' ||
            coalesce(technical_analysis, '') || ' ' ||
            coalesce(evidence_summary, '')
        ) @@ plainto_tsquery('simple', 'credential access')
        LIMIT 100
        """,
        ("ix_report_version_public_fts",),
    ),
)


def _index_names(plan: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(plan, dict):
        index_name = plan.get("Index Name")
        if isinstance(index_name, str):
            names.add(index_name)
        for value in plan.values():
            names.update(_index_names(value))
    elif isinstance(plan, list):
        for value in plan:
            names.update(_index_names(value))
    return names


def _contains_node_type(plan: Any, node_type: str) -> bool:
    if isinstance(plan, dict):
        if plan.get("Node Type") == node_type:
            return True
        return any(_contains_node_type(value, node_type) for value in plan.values())
    if isinstance(plan, list):
        return any(_contains_node_type(value, node_type) for value in plan)
    return False


async def verify_query_plans(session: AsyncSession) -> tuple[QueryPlanResult, ...]:
    """Run all representative plans and return the indexes PostgreSQL selected."""

    results: list[QueryPlanResult] = []
    for check in QUERY_PLAN_CHECKS:
        explained = await session.scalar(
            text(f"EXPLAIN (FORMAT JSON) {check.statement}")
        )
        if not isinstance(explained, list) or not explained:
            raise RuntimeError(f"PostgreSQL returned no plan for {check.name}")
        used = tuple(sorted(_index_names(explained[0])))
        results.append(
            QueryPlanResult(
                name=check.name,
                expected_indexes=check.expected_indexes,
                used_indexes=used,
                plan=explained[0],
            )
        )
    return tuple(results)
