# Plan 04: Non-destructive Hermes profile reconciler

## Objective

Replace one-shot profile bootstrap behavior with a safe reconciler that
materializes managed CTI-Hermes assets while preserving operator-owned runtime
state, credentials, sessions, logs, gateway state, and history.

## Scope

Cover profile path resolution, placeholder validation, managed-file ownership,
idempotent reconciliation, cron/job materialization, and migration reporting.
Do not overwrite an existing runtime profile as a side effect of normal
installation. Destructive replacement remains an explicit, separately
approved operation.

## Current baseline

- `.hermes/profiles/cti-analyst` and `cti-maintainer` contain repository assets,
  but some configs use literal `/home/$USER/...` paths and unresolved model or
  provider placeholders.
- `scripts/install-hermes-profiles.sh` localizes paths after copying and has a
  `--replace` flow that moves an entire destination before replacing it.
- `scripts/install-hermes-jobs.sh` does not materialize all manifest fields such
  as toolsets, preflight, skills, and monitor behavior.
- Maintainer recovery prompts contain an unresolved incident placeholder.
- Existing `docs/HERMES_PROFILE_MIGRATION.md` describes intended behavior but
  the scripts do not fully enforce it.

## Implementation sequence

1. Define a manifest of managed assets and protected runtime assets. Managed
   files may be updated; `.env`, token files, sessions, logs, gateway state,
   audit history, and operator extensions must be preserved by default.
2. Resolve repository, runtime, profile, and service URLs before writing.
   Validate that no `$USER`, staging absolute path, model placeholder, provider
   placeholder, or unresolved incident token remains in materialized assets.
3. Reconcile files atomically with mode preservation and a dry-run diff. Write
   a manifest containing source hash, destination hash, owner, and timestamp.
   Never follow symlinks outside the selected profile root.
4. Reconcile cron jobs from the manifest, including toolsets, preflight,
   profile, workdir, prompt, monitor/wake behavior, and schedule. Detect and
   report unmanaged conflicting jobs rather than silently replacing them.
5. Add migration output that clearly separates created, updated, preserved,
   skipped, and blocked assets. Require an explicit confirmation for any
   destructive replacement and create a recoverable backup before it.
6. Update the migration guide with dry-run, verification, and rollback steps.

## Likely files

- `scripts/install-hermes-profiles.sh`
- `scripts/install-hermes-jobs.sh`
- `.hermes/profiles/cti-analyst/config.yaml`
- `.hermes/profiles/cti-maintainer/config.yaml`
- `.hermes/profiles/cti-maintainer/prompts/recovery.md`
- `.hermes/profiles/*/cron/*.json`
- `.hermes/profiles/cti-maintainer/scripts/health-watchdog.sh`
- `docs/HERMES_PROFILE_MIGRATION.md`
- Installer and shell tests under `tests/` or `scripts/tests/`

## TDD and verification

Use temporary runtime roots and test:

- first install creates the expected managed assets and protected modes;
- second install is idempotent and produces no unnecessary changes;
- changed managed assets reconcile while `.env`, sessions, logs, gateway state,
  and history remain byte-for-byte preserved;
- path and URL localization leaves no placeholders or staging paths;
- manifest fields become equivalent installed job behavior;
- symlink/path traversal attempts are rejected;
- dry-run reports changes without writing;
- interrupted writes leave the previous valid file intact;
- explicit replacement creates a recoverable backup and is never implicit.

Run shell syntax checks plus Ruff/mypy/pytest for any Python helpers. Do not
run the installer against a real Hermes home during automated tests.

## Acceptance criteria

- Reconciliation is idempotent, atomic, and non-destructive by default.
- Managed and protected assets are documented and enforced in code.
- Installed profiles contain resolved paths and no unresolved placeholders.
- Cron jobs reflect the reviewed manifest, including safety controls.
- A dry-run and a machine-readable reconciliation report exist.

## Dependencies and hand-off

Plans 01–03 provide the service endpoints and profile consumers that must be
represented in prompts and jobs. Plan 05 depends on correct watchdog and job
materialization. Plan 06 must install both profiles into isolated temporary
roots and prove they do not share credentials or state.

## Rollback

Reconciliation must retain the previous managed-file manifest and a recoverable
backup for each changed file. Roll back the manifest version and managed files;
never restore protected runtime state from a repository copy.

