# Plan 07: Production promotion and historical backfill

## Objective

Promote the merged reliability work to the running CTI-Hermes application and,
when required, update historical entries through an explicit,
provenance-preserving backfill. This plan is designed to be executed in a new
session by an authorized deployment owner.

The repository already contains the completed Plans 01–06 on `main`. This is
an operational promotion and data-maintenance plan, not another Git backport.
The exact source revision, image digest, migration state, approval, and
evidence package must be recorded before production is changed.

## Safety boundaries

- Never put tokens, passwords, private keys, production environment files, or
  database dumps in Git, logs, evidence, or chat.
- Do not use a mutable image tag in production. Every deployment and rollback
  target must use `name@sha256:<64 hex characters>`.
- Do not use `--replace` for existing Hermes profiles unless an explicit
  recoverable replacement is approved. The normal reconciler preserves `.env`,
  sessions, logs, gateway state, audit history, memories, and operator files.
- Do not rewrite published report versions or source provenance in place.
- A successful application deployment does not authorize a historical
  backfill. Treat backfill as a separate change with its own approval.
- Stop on any failed gate, unexpected record-count change, provenance loss,
  profile-isolation failure, stale monitor state, invalid receipt, or failed
  health check. Retain failed evidence and restore the last verified immutable
  deployment when rollback is safe.

## Required inputs

Set these values in the operator session without committing them:

```bash
export APP_ROOT=/opt/cti-hermes/app
export ENV_FILE=/opt/cti-hermes/env/production.env
export SECRET_DIR="$HOME/.local/state/cti-hermes/secrets"
export REGISTRY=ghcr.io/mrcoggsworth
export IMAGE_NAME=threat-intel-agent
export APPROVAL_REFERENCE=<approved-change-id>
export APPROVAL_IDENTITY=<authorized-operator>
export PRIVATE_SERVICE_URL=https://ops.cti-hermes.home.arpa
export ANALYST_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9443
export HERMES_MODEL=<approved-model>
export HERMES_PROVIDER=<approved-provider>
export HERMES_PUBLIC_BASE_URL=http://127.0.0.1:18000
```

Also identify the prior deployment receipt and its immutable rollback image:

```bash
export ROLLBACK_RECEIPT=/var/lib/cti-hermes/deployment-receipts/<prior-receipt>.json
export ROLLBACK_IMAGE=<registry>/<image>@sha256:<prior-64-hex-digest>
export BACKUP_METADATA=/backups/latest.metadata
```

If any required value is unknown, stop and obtain it from the deployment
owner. Do not invent a digest, migration revision, receipt, or approval.

## Phase 0 — Establish the exact source and baseline

Run from a clean deployment checkout or a clean disposable clone:

```bash
cd "$APP_ROOT"
git fetch origin main --tags
git checkout main
git pull --ff-only origin main
export SOURCE_REVISION="$(git rev-parse HEAD)"
git status --short
```

The working tree must be clean. Record the following baseline before any
change:

- current image digest and deployment receipt
- current database migration revision
- current report, CVE, IOC, source-document, and published-projection counts
- current `/health/live`, `/health/ready`, run-status, heartbeat, and backup
  state
- current profile job IDs and ownership records
- current generated portal/feed counts if a static export is deployed

Use the existing private status and database commands; never include token
values in captured output:

```bash
uv run hermes-cti db status
uv run hermes-cti db verify-query-plans \
  --dataset-label production-sized \
  --output /restricted/evidence/query-plans-before.json
```

## Phase 1 — Build and attest an immutable application image

Build from `SOURCE_REVISION` in a clean builder environment. The repository’s
runtime updater does not build mutable images.

```bash
cd "$APP_ROOT"
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
npm ci
npm run build:css
docker build --file deploy/Dockerfile \
  --tag "$REGISTRY/$IMAGE_NAME:$SOURCE_REVISION" .
docker push "$REGISTRY/$IMAGE_NAME:$SOURCE_REVISION"
export IMAGE="$(docker inspect --format='{{index .RepoDigests 0}}' \
  "$REGISTRY/$IMAGE_NAME:$SOURCE_REVISION")"
case "$IMAGE" in *'@sha256:'*) ;; *) echo "image is not digest pinned" >&2; exit 2 ;; esac
```

Record the full image reference and verify that the registry resolves the same
digest. Preserve the build logs and test results in the restricted evidence
directory. Do not continue if the digest changes between push and deploy.

## Phase 2 — Reconcile Hermes profiles and jobs

First run a dry run and review the machine-readable report:

```bash
cd "$APP_ROOT"
scripts/install-hermes-profiles.sh \
  --repo "$APP_ROOT" \
  --runtime-root "$HOME/.hermes/profiles" \
  --private-service-url "$PRIVATE_SERVICE_URL" \
  --analyst-service-url "$ANALYST_SERVICE_URL" \
  --model "$HERMES_MODEL" \
  --provider "$HERMES_PROVIDER" \
  --dry-run > /restricted/evidence/profile-reconcile-dry-run.json
```

Confirm that the report contains no unsafe paths or unresolved placeholders,
and that protected state is marked preserved. Then apply the reconciliation:

```bash
scripts/install-hermes-profiles.sh \
  --repo "$APP_ROOT" \
  --runtime-root "$HOME/.hermes/profiles" \
  --private-service-url "$PRIVATE_SERVICE_URL" \
  --analyst-service-url "$ANALYST_SERVICE_URL" \
  --model "$HERMES_MODEL" \
  --provider "$HERMES_PROVIDER" \
  > /restricted/evidence/profile-reconcile.json
```

Verify both profile roots independently. The analyst profile must not contain
maintainer credentials, maintainer jobs, or maintainer-only runtime state. The
maintainer profile must not contain analyst credentials or analyst sessions.
The retired `cti-maintainer-approved-release` job must not be present; the
script-only watchdog must remain configured with `wakeAgent: false` and
`preflight: "always"`.

## Phase 3 — Disposable canary deployment

Before production, use a disposable Compose project and sanitized environment
inputs. Do not mount production secrets or production volumes.

```bash
cd "$APP_ROOT"
docker compose --file deploy/docker-compose.dev.yml config
docker compose --file deploy/docker-compose.dev.yml up --detach postgres
docker compose --file deploy/docker-compose.dev.yml run --rm web hermes-cti db migrate
docker compose --file deploy/docker-compose.dev.yml up --detach web
curl --fail --silent http://127.0.0.1:8000/health/live
curl --fail --silent http://127.0.0.1:8000/api/v1/public/reports
docker compose --file deploy/docker-compose.dev.yml down --volumes
```

Retain the exact source revision, image digest, migration revision, monitor
evidence, smoke output, and canary decision. Stop and retain the disposable
environment for diagnosis if a criterion fails; do not delete failed evidence.

## Phase 4 — Approved production deployment

Confirm the prior rollback receipt is valid, the backup metadata path is
ready, and migration compatibility has been reviewed. Then invoke the
approval-gated deployment exactly once:

```bash
cd "$APP_ROOT"
export HERMES_DEPLOY_APPROVED=true
export HERMES_APPROVAL_REFERENCE="$APPROVAL_REFERENCE"
export HERMES_APPROVAL_IDENTITY="$APPROVAL_IDENTITY"
export HERMES_IMAGE="$IMAGE"
export HERMES_SOURCE_REVISION="$SOURCE_REVISION"
export HERMES_MIGRATION_REVISION=<verified-alembic-head>
export HERMES_MIGRATION_COMPATIBLE=true
export HERMES_ENV_FILE="$ENV_FILE"
export HERMES_ENV_CHECKSUM="$(sha256sum "$ENV_FILE" | awk '{print $1}')"
export HERMES_BACKUP_METADATA_FILE="$BACKUP_METADATA"
export HERMES_ROLLBACK_IMAGE="$ROLLBACK_IMAGE"
export HERMES_ROLLBACK_RECEIPT="$ROLLBACK_RECEIPT"
export HERMES_RECEIPT_DIR=/var/lib/cti-hermes/deployment-receipts
scripts/deploy-approved.sh \
  > /restricted/evidence/deployment-output.txt \
  2> /restricted/evidence/deployment-errors.txt
```

The script validates approval, image immutability, environment checksum,
rollback receipt, backup readiness, Compose configuration, migrations, smoke,
and health before writing a secret-free hash-chained deployment receipt.

## Phase 5 — Post-deployment verification

Run checks from the deployment host and record status without recording token
values:

```bash
curl --fail --silent "$HERMES_PUBLIC_BASE_URL/health/live"
curl --fail --silent "$HERMES_PUBLIC_BASE_URL/health/ready"
uv run hermes-cti db status
uv run hermes-cti db verify-query-plans \
  --dataset-label production-sized \
  --output /restricted/evidence/query-plans-after.json
python3 scripts/deployment_receipt.py --verify \
  /var/lib/cti-hermes/deployment-receipts/<new-receipt>.json
```

Run the monitor and confirm that healthy state is quiet, while any actionable
state has a corresponding operator decision and recovery audit event. Confirm
that public routes expose only published records and private routes require
the correct scoped credentials.

If health or monitor acceptance fails, stop further rollout and use the
explicit `HERMES_ROLLBACK_IMAGE` through the approved deployment workflow.
Do not rebuild an image during rollback and do not reverse an irreversible
migration automatically.

## Phase 6 — Refresh existing portal entries

Classify the requested update before changing data:

### A. UI, template, CSS, or route changes only

No historical data rewrite is required. Deploying the new image makes dynamic
entries render with the new templates. If the deployment includes a checked-in
static export, regenerate it from the existing export data:

```bash
uv run hermes-cti rebuild-all --output-dir portal
```

Verify generated report, CVE, IOC, failure, and STIX counts against the
baseline. This command rebuilds presentation assets; it does not recalculate
historical intelligence.

### B. New derived intelligence fields or changed analysis behavior

The repository currently has no dedicated historical backfill command. Do not
use `rebuild-all` or an unrestricted live `sync-db` run as a substitute. Start
a separate implementation change for an idempotent command with this shape:

```text
hermes-cti db backfill \
  --source-artifacts <retained-artifact-store> \
  --from <UTC-time-or-record-id> \
  --to <UTC-time-or-record-id> \
  --batch-size <bounded-integer> \
  --dry-run | --apply
```

The backfill implementation must:

1. Acquire an approved change reference and create a verified database backup.
2. Read retained raw artifacts and source documents by stable IDs and hashes;
   do not silently replace canonical URLs or publication timestamps.
3. Re-run only the requested extraction, enrichment, correlation, or report
   validation stages using the current application revision.
4. Use deterministic idempotency keys and a resumable checkpoint. A repeated
   batch must produce no duplicate observations, entities, or report versions.
5. Preserve `source_document_id`, raw-artifact hash, canonical URL, retrieval
   time, publication time, processing origin, and original lifecycle state.
6. Write new immutable observations or report versions. Never mutate an
   already-published version in place.
7. Keep proposed, rejected, superseded, and unpublished results private. New
   public output requires the existing review/publication policy.
8. Emit a secret-free manifest containing input counts, output counts,
   skipped/failed IDs, provenance checks, code revision, and completion state.
9. Rebuild public projections/feeds only after the batch is complete and
   approved, then verify public/private isolation and output counts.

Run the first backfill in a disposable database restored from the production
backup. Compare before/after counts, sample provenance, lifecycle states,
public membership, and deterministic rerun results. Only then request a
production backfill approval.

## Evidence package

Retain these artifacts under a restricted, operator-controlled path:

| Evidence | Required contents |
| --- | --- |
| Source | exact `SOURCE_REVISION`, clean-tree result |
| Build | test/lint/type/CSS results and immutable image digest |
| Profiles | dry-run and apply reports, protected-state and job checks |
| Canary | Compose config, migration result, smoke output, monitor evidence, decision |
| Deployment | approval reference/identity, env checksum, backup metadata, receipt and rollback receipt |
| Runtime | health, run-status, heartbeat, backup, query-plan, and public/private checks |
| Backfill | dry-run/apply manifests, checkpoints, input/output counts, provenance samples, rerun result |

Evidence must contain references and hashes, not secret values. Retain failed
evidence for diagnosis according to the backup and operational retention
policy.

## Completion criteria

- `main` is deployed from the recorded source revision using the recorded
  immutable image digest.
- The deployment receipt verifies and points to a valid immutable rollback
  target.
- Both Hermes profiles reconcile without crossing secrets, sessions, history,
  or job ownership.
- Health, monitor, backup, migration, smoke, and query-plan checks pass.
- UI-only updates are visible after deployment/rebuild, with counts unchanged.
- Any data backfill is separately approved, idempotent, provenance-preserving,
  review-safe, and verified in a disposable database before production.
- The evidence package is complete and contains no secrets.

## Rollback

On any stop trigger, stop the canary or backfill, retain all evidence, and
notify the approval owner. For an application failure, redeploy the last
verified immutable image through the approved rollback workflow and verify
health again. For a data-backfill failure, stop at the checkpoint and restore
the verified pre-backfill database snapshot; do not delete failed manifests or
receipts. Do not mark the rollout complete until the rollback or exception is
formally recorded.
