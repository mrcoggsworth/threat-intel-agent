# CTI-Hermes data-model and historical-correlation gap review

Review basis: the supplied **CTI-Hermes Data Model and Historical Correlation
Specification**, the active SQLAlchemy metadata, Alembic revisions, persistence
repositories, portal routes, and the Phase 4–9 tests. This review is intended to
block deployment until the required data contracts are either implemented or
explicitly accepted as deferred scope.

## Executive result

The repository has a strong Phase 4–8 foundation: ingestion runs, source runs,
operational events, sources, immutable raw artifacts, versioned source
documents, evidence claims, indicators/observations, CVEs, products, affected
products, ATT&CK techniques, enrichment, risk assessments, relationships,
candidates, contradictions, resurfacing events, reports, report versions,
hunting, remediation, detections, publication, and model-run metadata are
represented.

It is not yet fully specification-complete. This pass closes the checkpointed
provenance, model-run, report-FK, public-projection, DM-003 lifecycle, and
DM-009 vulnerability-enrichment blockers. Representative DM-006 and
backup/restore verification are complete; production-sized plan capture and
explicit acceptance of the remaining P2 operational scope remain.

## Gap register

### P0 — must close before deployment

| ID | Status | Gap | Evidence | Required action |
| --- | --- | --- | --- | --- |
| DM-001 | Closed for persistence/read boundary | No normalized `threat_actor`, `malware`, `tool`, `campaign`, or `infrastructure` tables. Relationships can reference these entity types only as unvalidated polymorphic UUIDs. | `entity_models.py` adds normalized keys, aliases/metadata, temporal fields, status, and the tables are registered in `Base.metadata`. | Repository upserts now cover all normalized entities and public reads resolve only published memberships. |
| DM-002 | Closed | Durable records do not consistently carry `created_at`, `updated_at`, `record_status`, or `created_by_origin`. | `TimestampMixin` is applied to all durable tables and migration `0005_data_model_contracts` backfills UTC defaults. | Set explicit origins at each persistence boundary and add audit-field assertions to upgraded-database checks. |
| DM-003 | Closed | Several specification integrity rules existed only in Pydantic or prose. | Central lifecycle registry covers all 19 persisted lifecycle columns plus shared record status; migration `0009_lifecycle_checks` adds PostgreSQL checks and repository/PostgreSQL rejection tests pass. | Keep the registry synchronized with contract enums when new states are introduced. |
| DM-004 | Closed for required write boundaries | Evidence provenance was uneven and several artifacts used JSONB ID lists. | `entity_evidence` is now normalized and deterministic indicator/CVE extraction writes evidence links; safe FKs were added for relationship evidence. | Keep normalized evidence writes covered by PostgreSQL regression tests as new artifact types are added. |

### P1 — required for a complete operational contract

| ID | Status | Gap | Evidence | Required action |
| --- | --- | --- | --- | --- |
| DM-005 | Closed | Safe operational, evidence, supersession, rollback, model-run, and report current-version foreign keys now cover the unambiguous relationships. | Migrations `0005_data_model_contracts`, `0006_audit_projection`, and `0007_report_current_version` enforce the links; the report current-version FK is deferred for transaction-compatible write ordering. | Keep migration tests covering fresh, upgraded, and rollback paths. |
| DM-006 | Closed for representative access paths; production verification pending | Minimum indexes now cover run schedule, source-document hashes, relationship endpoints, report state/time, published report/entity membership, normalized entity evidence, vulnerability, product, ATT&CK, seen timestamps, and published report full text. | Migration `0010_query_plan_indexes` adds the public-membership index; `db verify-query-plans` and PostgreSQL integration coverage run representative `EXPLAIN (FORMAT JSON)` checks. | Run the verifier against a representative production-sized dataset and retain the JSON result with the deployment evidence. |
| DM-007 | Closed for model-assisted boundaries | Model execution now has a repository; relationship proposals and model-generated report bundles create secret-free model-run audit records with output, prompt, skill, token, and cost metadata fields. | `ModelRunRepository`, `CorrelationRepository.persist_model_proposal`, and `ReportRepository.persist_bundle` write deterministic audit records. | Require model callers to supply real system/skill hashes and triggering run IDs; the persistence boundary now records them without secrets. |
| DM-008 | Closed | Public entity and relationship schemas/routes now expose only natural public keys and require published-report membership; drafts and unreviewed relationships are excluded. | `entity_repository.py`, `entity_contracts.py`, and `/api/v1/public/entities` plus `/relationships` are covered by API tests. | Keep PostgreSQL projection coverage for published, draft, and rejected fixtures as entity types expand. |

### P2 — important completeness and maintainability work

| ID | Gap | Evidence | Required action |
| --- | --- | --- | --- |
| DM-009 | **Closed.** Vulnerability fields are now first-class and provider snapshots are retained in a normalized observation table with field-level canonical-selection provenance. | Vulnerability and typed contracts include CWE, CVSS version/vector, EPSS percentile/date, KEV dates/action, and controlled exploitation state; migrations 0011_vuln_field_contracts and 0012_vuln_observation_backfill add schema and backfill; persistence, report, and published-entity projections are covered by tests. | Keep provider precedence explicit, preserve observations, and extend the selection registry when new fields are added. |
| DM-010 | `Source`, `RawArtifact`, and `SourceDocument` cover the core ingestion contract, but raw-artifact storage policy, retention metadata, and source configuration history are not fully operationalized. | Storage locator/payload exist, while retention is described mainly in runbooks. | Add retention/locator policy fields and a scheduled retention/restore verification procedure. |
| DM-011 | Lifecycle values were duplicated across `state`, `status`, `review_state`, and `active`. | `db/lifecycle.py` now centralizes the allowed values and migration `0009_lifecycle_checks` applies database checks; `active` remains an intentional boolean relationship flag. | Document the policy in the P2 operational scope and extend the registry when new state fields are introduced. |
| DM-012 | Soft deletion is not modeled. This is acceptable for immutable evidence, but needs an explicit policy for mutable entities and reports. | No `deleted_at` columns. | Document “no deletion for evidence/history” and add soft deletion only to entities that require it. |

## P2 deployment scope decision record

DM-010 through DM-012 are proposed deployment exceptions, not silently accepted requirements. Before the approved deployment workflow runs, an authorized deployment owner must record acceptance for the following deferred scope:

- DM-010: raw-artifact retention scheduling and source-configuration history remain operational follow-up; immutable payload and storage-locator fields are retained.
- DM-011: lifecycle values remain centralized in `db/lifecycle.py`; new lifecycle fields must be added to the registry and migration checks.
- DM-012: evidence and history are never deleted; soft deletion is deferred until a mutable public entity requires it.

The acceptance record must identify the owner, scope, risk treatment, and target follow-up for each exception.

## Verification checkpoint

- Representative PostgreSQL query-plan checks pass through `db verify-query-plans` and integration coverage; production-sized plan JSON is still required.
- Encrypted custom-format backup creation, SHA-256 metadata, `pg_restore --list`, and isolated restore verification passed in disposable PostgreSQL containers on 2026-08-25.
- No production deployment, retention deletion, or production restore was performed by this review.

## Existing strengths confirmed

- PostgreSQL is the persistence boundary for historical data; intelligence is
  not delegated to profile memory.
- Ingestion idempotency and the daily advisory lock are implemented.
- Raw artifacts have an immutability trigger and source/content deduplication.
- Source documents create versions using `supersedes_id` and
  `document_version`.
- Indicator natural keys, CVE natural keys, product keys, relationship keys,
  candidate records, contradiction records, and resurfacing transitions exist.
- Model-inference relationships are kept proposed/reviewed and public
  relationship queries require active reviewed state.
- Report versions, detection artifacts, hunts, remediation, publication
  records, validation manifests, and rollback targets are persisted.
- Public portal reads published report state and does not expose private
  operational endpoints through the public proxy.

## Implementation sequence before deployment

1. **Schema completion:** add normalized threat entities, shared audit fields,
   evidence links, safe foreign keys, checks, and minimum indexes.
2. **Persistence completion:** add entity upserts, evidence-link writes,
   model-run audit writes, vulnerability/provider field persistence, and
   correlation queries over the normalized entities.
3. **Public projection completion:** add explicit public schemas/queries for
   approved entities and reviewed relationships; add negative tests for drafts,
   rejected proposals, provider metadata, prompts, and operational errors.
4. **Migration and compatibility verification:** run the new migration against
   a fresh database and a representative upgraded Phase 8 database; verify
   immutability, idempotent reruns, backup/restore, and rollback compatibility.
5. **Performance and retention verification:** inspect query plans, confirm
   indexes are used, exercise configured retention, and perform an isolated
   restore before deployment approval.

Current checkpoint: lifecycle hardening, DM-009 vulnerability-field implementation, representative DM-006 access-path verification, and disposable backup/restore verification are complete. The next work is production-sized plan capture and explicit acceptance of the remaining P2 operational scope before the approved deployment workflow can run.

Deployment can move to the deployment stages after production-sized DM-006 plan capture and explicit P2 acceptance are complete or recorded as documented exceptions. Backup/restore verification is complete for the disposable rehearsal; the approved deployment script remains the production gate.
