# Plan 03: Bounded analyst corpus queries

## Objective

Give the analyst profile a bounded, read-only API for historical correlation
across the persisted CTI corpus. Queries must be paginated, authorized,
deterministically ordered, and safe for repeated analyst workflows.

## Scope

Add private analyst read contracts/routes/repository queries for CVEs, IOCs,
products and versions, actors, malware, tools, campaigns, ATT&CK techniques,
URLs, evidence, relationships, and contradictions. Include provenance and
status filters needed to distinguish published, reviewed, proposed, rejected,
and superseded records. Do not expose these routes through the public portal.

## Current baseline

The analyst API provides run status, run detail, evidence, proposals, report
validation, and submission flows, but no bounded historical corpus search. The
Hermes analyst prompts require historical correlation, while the normalized
entity, evidence, relationship, vulnerability, and contradiction tables already
provide most of the persistence foundation.

## Implementation sequence

1. Define a common private query contract: limit with a hard maximum, stable
   cursor or keyset pagination, deterministic sort, query timeout, allowed
   filters, result count semantics, and a provenance envelope. Reject arbitrary
   SQL, unbounded full-text scans, and user-controlled sort expressions.
2. Map each domain query to repository methods using existing natural keys and
   indexes. Prefer one bounded query per resource family and avoid N+1
   evidence/provenance loading.
3. Add analyst routes under the existing private authorization boundary. Keep
   public entity/relationship projections separate and enforce lifecycle and
   publication filters at the repository boundary, not only in route code.
4. Add relationship and contradiction views that include the supporting
   evidence IDs, review state, confidence, timestamps, and supersession links.
5. Update analyst prompts or client helpers only after the API contract is
   stable; document examples that use narrow filters rather than “load all”.

## Likely files

- `src/hermes_cti/analyst/routes.py`
- `src/hermes_cti/analyst/` service/repository modules
- `src/hermes_cti/db/entity_repository.py`
- `src/hermes_cti/db/repositories.py`
- `src/hermes_cti/models/contracts.py` and `models/__init__.py`
- `src/hermes_cti/api/` authorization and route registration
- `src/hermes_cti/db/query_plans.py` and Alembic only if indexes are needed
- `.hermes/profiles/cti-analyst/prompts/` documentation consumers

## TDD and verification

Test each resource family with:

- exact natural-key lookup and bounded filtered search;
- cursor pagination with no duplicates or skipped rows across pages;
- hard-limit enforcement and invalid-filter rejection;
- private-token authorization and public-route denial;
- draft, rejected, proposed, superseded, and unpublished records excluded or
  explicitly labeled according to the contract;
- evidence/provenance included without prompts, secrets, or raw credentials;
- relationship and contradiction results stable under repeated reads;
- representative PostgreSQL `EXPLAIN` checks for the new query paths.

Run the Python workflow gates and the database migration checks if indexes or
contracts change. Add API contract tests for the exact JSON shape.

## Acceptance criteria

- Analysts can answer the supported historical-correlation questions without
  direct database access or profile-memory backfill.
- Every endpoint has a hard bounded result size and stable pagination.
- Lifecycle, publication, and authorization rules are enforced server-side.
- Query plans use the intended indexes at representative data volume, or the
  endpoint is explicitly deferred with a documented limit.
- Public routes cannot be used to retrieve private corpus detail.

## Dependencies and hand-off

Plan 01 supplies authoritative run-status context, and Plan 02 supplies clean
source provenance. Plan 06 must exercise the analyst profile against a seeded
historical corpus and verify cross-profile isolation.

## Rollback

Release the routes disabled by default or behind the private API feature gate.
Because this is additive read functionality, rollback should remove route
registration while retaining migrations and data needed by existing code.

