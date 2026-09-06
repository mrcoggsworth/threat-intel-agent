# Plan 02: Typed source request contracts and fixtures

## Objective

Make every configured source executable from a typed, testable request
contract. Support source-specific HTTP method, request body, headers, expected
content type, parser selection, and retry policy without scattering exceptions
through ingestion code.

## Scope

Cover source configuration validation, request construction, response
validation, retry classification, and representative fixtures. Treat
`config/sources.json` as the authoritative registry. Do not redesign the
historical analyst API or profile installation in this plan.

## Current baseline

- `config/sources.json` contains the active source registry.
- `http_client.py` is effectively GET-oriented and does not consume the
  existing `adapter_settings` field as a complete request contract.
- Expected content type and source-specific request behavior are not enforced
  centrally.
- Some connection failures are classified immediately rather than following a
  consistent bounded retry taxonomy.
- Collection persistence currently records artifact metadata but does not pass
  the fetched payload into `persist_raw_artifact()`; decide explicitly whether
  payload retention is part of this implementation or a follow-up.

## Implementation sequence

1. Define immutable Pydantic contracts for request method, URL parameters,
   headers, body encoding, expected response content types, parser adapter, and
   bounded retry policy. Reject unsupported methods, malformed URLs, invalid
   content types, and secret-bearing checked-in configuration.
2. Add a source-config validation command/test that loads every entry in
   `config/sources.json` and reports the source identifier for each failure.
3. Refactor the HTTP client to build requests only from the typed contract.
   Normalize timeout, DNS/connect, TLS, HTTP status, content-type, and body
   errors into stable ingestion error categories. Retry only bounded,
   explicitly retryable failures with jitter and a request budget.
4. Repair or add fixtures for each adapter family: JSON API, RSS/XML, HTML,
   PDF, POST-backed source, and an expected failure. Include official source
   response shapes and content-type mismatches.
5. Wire source outcomes to the source freshness fields and collection audit
   records, preserving URL, publication time, collection time, and processing
   status. If raw payload persistence is deferred, document the retention
   decision and add a test preventing accidental false claims.

## Likely files

- `src/hermes_cti/ingestion/http_client.py`
- `src/hermes_cti/ingestion/source_config.py`
- `src/hermes_cti/models/contracts.py`
- `src/hermes_cti/ingestion/normalization.py`
- `src/hermes_cti/ingestion/service.py`
- `config/sources.json`
- Source adapter modules and `tests/` ingestion fixtures
- `src/hermes_cti/db/models.py` and repositories only if freshness/payload
  persistence is changed

## TDD and verification

First add tests for contract parsing and request snapshots. Then cover:

- GET and POST request construction, including body and content type;
- per-source headers without logging credentials;
- valid and invalid response content types;
- retryable timeout/connect/rate-limit/5xx behavior and non-retryable 4xx,
  parse, and policy failures;
- fixture-based parsing for every configured adapter family;
- duplicate/canonical URL behavior and idempotent reruns;
- source freshness, failure count, and last-success updates;
- all 39 configured source entries load successfully.

Run Ruff, strict mypy, pytest, and the full frozen environment verification.
Use network-free fixtures in unit tests; reserve live-source checks for an
explicit operator-run smoke command.

## Acceptance criteria

- No source requires an undocumented special case in the HTTP client.
- Every active source has a validated request and response contract plus a
  deterministic fixture or an explicitly documented external dependency.
- Retry behavior is bounded, observable, and does not retry policy or parsing
  failures.
- Source failures update operational freshness data without corrupting
  successful historical evidence.
- No credentials, tokens, or private response bodies appear in logs or test
  fixtures.

## Dependencies and hand-off

Plan 01 should land first so source outcomes map to the corrected run-status
semantics. Plan 06 consumes these fixtures for deterministic cross-profile
end-to-end tests. The raw-payload retention decision must be recorded before
deployment planning, even if implementation is deferred.

## Rollback

Keep the prior adapter behavior behind a compatibility path while validating
the registry. Roll back the client and config changes together if a production
source cannot be represented by the typed contract; do not silently reintroduce
source-specific behavior outside the registry.

