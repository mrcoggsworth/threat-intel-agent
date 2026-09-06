# Plan 05: Monitor-gated recovery and immutable deployment receipts

## Objective

Make operational recovery safe and auditable. Recovery must be triggered only
by actionable monitor evidence, must not invoke an LLM for unchanged healthy
state, and must deploy only an immutable, preflight-verified artifact with a
durable receipt and rollback target.

## Scope

Cover monitor signal classification, recovery gating, approved-release
schedule safety, immutable image validation, deployment preflight, receipts,
and rollback metadata. Do not broaden this into a general deployment-platform
rewrite.

## Current baseline

- `scripts/monitor.py` checks liveness, readiness, last-success, heartbeat,
  backup metadata, disk, and optional certificate state, but does not fully
  distinguish latest attempt, full success, usable partial state, and heartbeat.
- The maintainer profile includes recurring approved-release and recovery jobs;
  recovery prompts contain unresolved incident context.
- `scripts/deploy-approved.sh` enforces immutable digest or `:vN`, while
  `scripts/update-app.sh` defaults to `cti-hermes:local` and does not create a
  complete immutable receipt.
- The watchdog has differing TLS behavior between profile and root copies;
  the `--insecure` path must not be accepted for production verification.

## Implementation sequence

1. Define monitor states and evidence requirements: healthy, degraded,
   actionable failure, stale data, unknown, and operator-required. Include
   signal timestamp, endpoint, observed status, and correlation/run IDs.
2. Gate recovery on actionable evidence and a cooldown/lock. A heartbeat alone
   cannot trigger ingestion recovery; unchanged healthy state must produce no
   LLM wake-up. Preserve an audit event for every suppressed, attempted, and
   completed recovery.
3. Remove or disable any recurring approved-release automation. Keep release
   execution explicitly approved and separate from watchdog recovery.
4. Add deployment preflight that requires an immutable image reference, source
   revision, migration compatibility, environment checksum, backup readiness,
   health endpoints, and an explicit rollback image/receipt target.
5. Persist a secret-free deployment receipt containing artifact digest,
   revision, migration result, verification timestamps, operator/approval
   identity, health evidence, and rollback target. Make the receipt append-only
   or otherwise tamper-evident.
6. Align watchdog TLS verification, timeout, and exit-code behavior across
   root scripts and profile copies. Fail closed when certificate verification or
   endpoint identity cannot be established.

## Likely files

- `scripts/monitor.py`
- `scripts/health-watchdog.sh`
- `.hermes/profiles/cti-maintainer/scripts/health-watchdog.sh`
- `.hermes/profiles/cti-maintainer/cron/*`
- `.hermes/profiles/cti-maintainer/prompts/recovery.md`
- `scripts/deploy-approved.sh`
- `scripts/update-app.sh`
- `deploy/docker-compose.yml`
- `deploy/OPERATIONS_ACCEPTANCE.md`
- `deploy/INTERNAL_ACCESS_MATRIX.md`
- Database model/repository and Alembic migration if receipts are persisted in
  PostgreSQL rather than an append-only deployment store

## TDD and verification

Test monitor decisions with controlled evidence:

- healthy unchanged state suppresses recovery;
- stale heartbeat and failed ingestion produce distinct actionable reasons;
- partial usable data does not masquerade as full success;
- cooldown and lock prevent duplicate recovery;
- recovery does not run an approved release;
- mutable image tags and missing digests fail preflight;
- receipts omit secrets and contain all required immutable identifiers;
- rollback target is present and machine-verifiable;
- TLS verification failure fails closed;
- monitor exit codes are stable for automation.

Run shell syntax checks, Python workflow gates, deployment smoke tests, and a
disposable Compose rehearsal. Do not run production deployment or recovery as
part of the test suite.

## Acceptance criteria

- No recurring job can deploy an approved release without explicit approval.
- Recovery is evidence-gated, deduplicated, auditable, and silent for unchanged
  healthy state.
- Deployment cannot proceed with a mutable or unverifiable artifact.
- Every approved deployment has a secret-free receipt and rollback target.
- Monitor, analyst, and deployment status use the same run semantics from
  Plan 01.

## Dependencies and hand-off

Plan 01 is required for correct monitor inputs. Plan 04 supplies safe profile
and job materialization. Plan 06 must exercise failure injection, recovery
suppression, preflight rejection, and receipt verification.

## Rollback

Keep the last verified immutable artifact and receipt available. Recovery code
must be able to restore the prior deployment without rebuilding or resolving a
mutable tag. If monitor behavior is incompatible, disable recovery automation
while retaining read-only monitoring and manual, approved rollback.

