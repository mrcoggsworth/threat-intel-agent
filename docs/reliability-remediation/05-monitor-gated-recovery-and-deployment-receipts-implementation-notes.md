# Plan 05 implementation notes

## Monitor and recovery gate

`scripts/monitor.py` retains the existing nonzero exit behavior while writing
two secret-free artifacts to the shared runtime volume:

- `monitor-evidence.json` is the latest atomic snapshot used by the recovery
  preflight.
- `monitor-events.jsonl` is the append-only observation history.

Each snapshot has a stable event ID, observation time, state, endpoint/status
where applicable, correlation ID, run ID where available, and individual
signals. The state classifier distinguishes healthy, unknown, actionable
failure, stale data, and operator-required conditions. A scheduler heartbeat
is only a signal; it cannot independently become an actionable ingestion
recovery event.

`scripts/recovery_gate.py` is intentionally separate from the recovery action.
It suppresses non-actionable evidence, enforces an atomic lock and cooldown,
and appends suppressed, attempted, and completed audit records. A recovery
caller must complete the acquired decision so the lock is released.

## Release and receipt controls

The maintainer profile no longer installs or schedules the recurring approved-
release job. Release execution remains an explicit operator action through
`scripts/deploy-approved.sh`.

The approved deployment preflight now requires:

- a digest-pinned application and rollback image;
- source and migration revisions;
- an explicit migration-compatibility result;
- an environment-file SHA-256 checksum;
- successful backup metadata;
- an existing rollback receipt target; and
- explicit approval reference and identity.

After smoke verification, `scripts/deployment_receipt.py` writes a new
0600 JSON receipt with `O_EXCL`, never overwriting a prior receipt. The receipt
contains only deployment identifiers, verification timestamps, migration and
backup status, health evidence, approval metadata, and rollback metadata. Its
content hash is chained to the previous valid receipt hash. The helper exposes
`verify_receipt()` for offline verification.

`scripts/update-app.sh` now consumes an existing digest-pinned image and does
not build or invent a mutable local tag. It is not a substitute for the
approval-gated deployment workflow.

## TLS and operator prerequisites

The root and maintainer watchdog scripts are byte-for-byte aligned and no
longer pass `curl --insecure`. HTTPS uses normal certificate and hostname
verification; an unavailable or invalid certificate is a failure. Operators
must provide `HERMES_TLS_CA_FILE` when a private CA is required.

Before an approved deployment, set `HERMES_ENV_CHECKSUM` to the SHA-256 of the
selected environment file, provide `HERMES_BACKUP_METADATA_FILE`, and identify
the prior immutable image and receipt through `HERMES_ROLLBACK_IMAGE` and
`HERMES_ROLLBACK_RECEIPT`. Do not place credentials in receipts, monitor
evidence, or audit logs.
