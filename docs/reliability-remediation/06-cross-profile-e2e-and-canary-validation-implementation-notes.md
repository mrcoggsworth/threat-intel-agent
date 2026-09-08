# Plan 06 implementation notes: cross-profile E2E and canary validation

Plan 06 is implemented as a deterministic, disposable validation layer in
`tests/test_plan06.py`. It exercises the production ingestion service,
analyst contract boundary, profile reconciler, monitor/recovery CLI, and
deployment receipt/preflight surfaces without contacting production services.

## Validation matrix

| Objective | Entrypoint | Fixture | Expected result | Retained evidence |
| --- | --- | --- | --- | --- |
| Ingestion | `IngestionService.collect_once` | `fixture-http-responses` | complete and failed-partial manifests retain successful documents | ingestion manifest assertion |
| Analyst | `CorpusQuery` and analyst/public routes | `historical-corpus-contracts` | bounded private queries; public corpus and drafts return 404 | analyst query assertion |
| Profiles | `install-hermes-profiles.sh` | temporary profile roots | dry-run is write-free; repeat/update preserves `.env` and operator files | reconciler report assertion |
| Operations | `monitor.py` and `recovery_gate.py` | health, heartbeat, backup, and run-status fixtures | healthy is suppressed; actionable failure is gated; CLI exit codes are distinct | monitor evidence and recovery audit |
| Deployment | `deploy-approved.sh` and `deployment_receipt.py` | digest-pinned rollback receipt | mutable image is rejected; valid receipt verifies and remains secret-free | receipt assertion |
| Canary | Plan 06 fixture manifest | disposable canary record | stop triggers and rollback target are declared before any rollout | `tests/fixtures/plan06_canary_manifest.json` |

The source-registry assertion also verifies that the authoritative registry
loads without network access and retains all eight configured threat
categories. Fixture collection validates provenance-bearing source documents,
full success, and partial failure semantics.

## Canary decision record

The checked-in canary manifest is a contract, not production approval. A real
disposable deployment must retain the exact source revision, digest-pinned
image, migration revision, environment checksum, monitor JSON/JSONL evidence,
deployment receipt, rollback receipt, and approval identity. Secrets and token
values must never be copied into the record.

Stop immediately and restore the last verified immutable receipt if any of the
following occurs: an unknown or actionable monitor state lacks an approved
decision; profile isolation or protected-state preservation fails; a private
credential crosses profile boundaries; an artifact or rollback target is not
digest pinned; migration, backup, receipt, or health preflight fails; or any
repository gate fails. Failed evidence is retained for diagnosis.

The harness intentionally does not authorize or perform a production
deployment. The repository gates run in CI; a deployment owner must execute a
separate disposable Compose rehearsal with real, approved environment inputs
and attach its resulting evidence package before production rollout.
