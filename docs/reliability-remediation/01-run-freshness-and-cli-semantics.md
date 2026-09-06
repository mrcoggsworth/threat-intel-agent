# Plan 01: Run freshness and CLI semantics

## Objective

Make ingestion health unambiguous. The API, analyst views, scheduler, monitor,
and `db run-daily` command must distinguish the latest attempt, the latest full
success, and the latest usable partial result. A failed parent run must not be
reported as a successful daily run.

## Scope

In scope are run-status contracts, repository queries, scheduler outcome
handling, analyst/operations projections, and CLI exit behavior. Keep the
scheduler heartbeat separate from ingestion success. Do not add historical
analyst query capabilities here; those belong to Plan 03.

## Current baseline

- `RunRepository.last_successful()` currently admits a failed run when it has
  successful sources, which makes partial failure look like success.
- `analyst/routes.py` repeats the same ambiguity in `_latest_run()`.
- `db/scheduler.py` invokes the pipeline but does not propagate its persisted
  outcome to the scheduler result.
- `cli/database_commands.py` reports completion after lock acquisition without
  checking the parent run outcome.
- Operations currently exposes `/api/v1/ops/last-success` and a separate
  scheduler-heartbeat endpoint, but not a complete status projection.

## Implementation sequence

1. Define a typed internal status model for `latest_attempt`,
   `latest_full_success`, `latest_usable`, and `scheduler_heartbeat`, including
   explicit `None` values and failure reasons. Preserve existing response
   fields where compatibility requires it.
2. Add repository methods with deterministic ordering and explicit predicates:
   full success must be a completed, non-failed run with all required source
   work satisfied; usable may be partial but must record its limitations.
3. Refactor analyst and operations routes to use those methods. Ensure a stale
   full success cannot hide a newer failed attempt.
4. Return a structured pipeline outcome from the scheduler path and make the
   CLI return nonzero for a persisted failed parent run, lock contention, or
   unusable outcome. Keep human-readable output concise and machine-readable
   fields stable.
5. Update monitor checks and templates to name the exact status being checked.
   Add a compatibility note for callers of `/last-success` before changing or
   deprecating it.

## Likely files

- `src/hermes_cti/db/repositories.py`
- `src/hermes_cti/db/scheduler.py`
- `src/hermes_cti/cli/database_commands.py`
- `src/hermes_cti/analyst/routes.py`
- `src/hermes_cti/portal/routes.py`
- `src/hermes_cti/models/contracts.py` or a new run-status contract module
- `src/hermes_cti/monitoring/` and `scripts/monitor.py`
- Relevant templates and API documentation

## TDD and verification

Add regression tests before changing behavior:

- completed run with all sources succeeds;
- failed run with some successful sources is not `latest_full_success`;
- partial run is returned only as `latest_usable`, with limitations;
- newest failed attempt is visible beside the older full success;
- heartbeat age does not imply ingestion success;
- CLI exits nonzero when the parent run fails or is unusable;
- lock contention remains distinguishable from pipeline failure;
- analyst and operations responses remain authorized and secret-free.

Run the repository gates from the Python workflow, including Ruff formatting,
Ruff checks, strict mypy, and pytest. Build CSS only if templates or CSS are
changed.

## Acceptance criteria

- No code path labels a failed parent run as a full success.
- Every status response identifies whether it describes an attempt, full
  success, usable partial result, or scheduler heartbeat.
- `db run-daily` is safe for automation: its exit code matches the persisted
  outcome.
- Monitor and analyst consumers have enough information to diagnose stale,
  failed, partial, and healthy states without reading the database directly.
- Existing clients either continue to work through a documented compatibility
  field or receive a deliberate, tested versioned change.

## Dependencies and hand-off

This is the first implementation plan. Plan 05 consumes its status contracts
for monitor-gated recovery. Plan 06 must exercise all status classes in the
cross-profile end-to-end suite.

## Rollback

Deploy behind the existing status endpoints or a feature flag if available.
Keep the old projection available until monitor and analyst clients have been
verified. Roll back route/CLI changes together if status fields and exit codes
would otherwise disagree.

