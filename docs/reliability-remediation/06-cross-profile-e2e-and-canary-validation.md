# Plan 06: Cross-profile E2E and canary validation

## Objective

Prove the six reliability objectives together across the analyst and maintainer
profiles, the API, ingestion pipeline, scheduler, monitor, deployment scripts,
and recovery controls before production approval.

## Scope

Build a deterministic, disposable end-to-end harness and a canary checklist.
Verify profile isolation, run semantics, source contracts, bounded analyst
queries, reconciler behavior, monitor gating, immutable receipts, and rollback
metadata. This plan validates earlier work; it should not introduce new product
behavior except test hooks required for safe determinism.

## Test environment

Use temporary Hermes profile roots, a disposable PostgreSQL instance, fixture
HTTP responses, and a local Compose stack. Seed a small historical corpus with
successful, partial, failed, proposed, reviewed, rejected, superseded, and
contradictory records. Use separate analyst and maintainer credentials and
assert that logs and receipts contain no secrets.

## Implementation sequence

1. Add a test matrix mapping each objective to its entrypoint, fixture, expected
   status, and evidence artifact. Include fresh install and upgrade from an
   existing runtime profile.
2. Run the ingestion scenario: source contracts load, fixtures collect, a
   complete run succeeds, a partial run is usable but not full success, and a
   failed parent run produces the correct CLI exit code and monitor state.
3. Run the analyst scenario: private historical queries paginate correctly,
   lifecycle/publication filters hold, provenance is present, and public routes
   cannot access private corpus data.
4. Run the profile scenario: reconciler dry-run, install, repeat install,
   managed update, protected-state preservation, job materialization, and
   placeholder/path validation.
5. Run the operations scenario: healthy monitor suppression, actionable failure
   recovery gating, cooldown, immutable deployment preflight rejection and
   success, receipt verification, and rollback-target validation.
6. Execute a canary against a disposable deployment. Record exact revisions,
   image digest, migration state, test results, monitor evidence, and approval
   identity. Define stop/rollback triggers before running it.

## Likely files

- New or expanded integration tests under `tests/`
- Test fixtures and local Compose/test configuration
- `scripts/` smoke, monitor, deployment, and restore verification scripts
- `.github/workflows/ci.yml`
- `deploy/OPERATIONS_ACCEPTANCE.md`
- `docs/HERMES_PROFILE_MIGRATION.md`
- All implementation files changed by Plans 01–05 only where test hooks are
  required

## Required repository gates

Run the complete target-repo sequence:

```text
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
npm run build:css
uv run python scripts/update-app.py --test --no-restart --no-migrate --no-verify
```

Use the repository's actual update command/options if the script interface
changes during Plans 04–05. Preserve artifacts from each gate in the canary
record; do not claim a gate ran when its dependency or service was unavailable.

## Acceptance criteria

- All six objective plans have at least one end-to-end assertion.
- Analyst and maintainer profiles cannot read or mutate one another's secrets,
  sessions, history, or runtime state.
- Full, partial, failed, stale, and heartbeat-only states remain distinct from
  ingestion through monitoring and CLI output.
- Source fixtures, historical queries, profile reconciliation, recovery gates,
  deployment receipts, and rollback metadata pass in a disposable environment.
- Full CI and deployment rehearsal gates pass, with retained evidence and an
  explicit canary stop/rollback decision.

## Dependencies and hand-off

This is the final plan and depends on Plans 01–05. It should be implemented
last. Its canary record becomes the evidence package for the approved
deployment owner; it does not itself authorize production deployment.

## Rollback

Stop the canary on any failed acceptance criterion, restore the last verified
immutable artifact, and retain the failed evidence. Do not delete test data or
receipts needed for diagnosis. Production rollout remains blocked until the
failed criterion is corrected or formally accepted as an exception.

