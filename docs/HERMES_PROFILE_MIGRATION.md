# Hermes profile migration and installation guide

This guide turns the repository-staged Hermes assets into two independent
local profiles:

- `cti-analyst` for public CTI analysis, historical correlation, report
  validation, and controlled publication requests.
- `cti-maintainer` for repository maintenance, CI, operations, deployment
  preparation, and explicitly approved release work.

The repository copy under `.hermes/profiles/` is safe to commit and review. A
runtime Hermes home must live outside the repository and must be private to
its profile. Never run both profiles against the same home, and never commit a
runtime `.env`, token, database URL, private key, session, or production log.

## Choose an installation path

### Beginner: guided local setup

Prerequisites:

- A local clone of this repository.
- Python 3.12+ and `uv` for the CTI-Hermes project.
- Hermes CLI installed and available as `hermes` if you want profile and cron
  creation performed automatically.
- A private service URL only if the CTI service is running. For a local
  development service, use a URL such as `http://127.0.0.1:8000`; for the
  home-server deployment, use the private hostname configured by the operator.

From the repository root:

```sh
chmod +x scripts/install-hermes-profiles.sh
scripts/install-hermes-profiles.sh --guided
```

The guided installer asks for the runtime root, private service URL, and
whether to create Hermes profiles and cron jobs. It creates separate homes
under the selected runtime root, for example:

```text
~/.hermes-profiles/
├── cti-analyst/
└── cti-maintainer/
```

After it finishes:

1. Edit each generated `.env` file. Replace model/provider placeholders and
   configure only the credential path intended for that profile.
2. Ensure the analyst token cannot be read by the maintainer and the
   maintainer token cannot be read by the analyst.
3. Run the printed `hermes profile show` and `hermes doctor` commands.
4. Manually trigger one analyst job and one maintainer diagnostic job before
   enabling recurring schedules.

The script creates `.env` from `.env.example` with mode `0600`, but it never
puts credentials into that file. Treat the file as an operator-owned template
until its placeholders are replaced.

### Intermediate: explicit, reviewable setup

Use explicit paths and skip actions you want to perform manually:

```sh
scripts/install-hermes-profiles.sh \
  --repo "$PWD" \
  --runtime-root "$HOME/.local/share/hermes-profiles" \
  --private-service-url "http://127.0.0.1:8000" \
  --no-cron
```

Review the generated files before using them:

```sh
find "$HOME/.local/share/hermes-profiles" -maxdepth 3 -type f | sort
diff -u .hermes/profiles/cti-analyst/config.yaml \
  "$HOME/.local/share/hermes-profiles/cti-analyst/config.yaml"
```

Create the native Hermes profiles manually if the CLI is not installed or its
home-location behavior is customized:

```sh
hermes profile create cti-analyst --description "Public CTI analyst"
hermes profile create cti-maintainer \
  --description "Approval-gated CTI-Hermes maintainer"
hermes --profile cti-analyst config set terminal.cwd "$PWD"
hermes --profile cti-maintainer config set terminal.cwd "$PWD"
```

Copy each generated profile directory into the native home reported by the
Hermes CLI. Do not merge the two directories and do not copy either
`memories/MEMORY.md` into the other profile.

Install cron jobs separately after review:

```sh
HERMES_REPOSITORY="$PWD" \
HERMES_PROFILE=cti-analyst \
HERMES_PROMPT_DIR="$HOME/.local/share/hermes-profiles/cti-analyst/prompts" \
scripts/install-hermes-jobs.sh

HERMES_REPOSITORY="$PWD" \
HERMES_PROFILE=cti-maintainer \
HERMES_PROMPT_DIR="$HOME/.local/share/hermes-profiles/cti-maintainer/prompts" \
scripts/install-hermes-jobs.sh
```

### Advanced: service-account and host isolation

For a home server or multi-user host:

1. Create two OS service accounts or two locked-down service identities.
2. Give each identity ownership of only its Hermes home, for example
   `/var/lib/hermes/cti-analyst` and `/var/lib/hermes/cti-maintainer`.
3. Set directory mode `0700`; set `.env` mode `0600`.
4. Give the analyst identity public web access and the analyst service token
   only. Do not grant Docker socket, production environment, database
   superuser, GitHub write, or deployment permissions.
5. Give the maintainer identity repository branch access and the minimum
   operational permissions needed for approved workflows. Do not grant it the
   analyst profile's credentials.
6. Restrict the private service endpoint at the network and application
   authorization layers. A private hostname is not an authorization boundary.
7. Pin the model and provider separately in each profile.
8. Run the health watchdog as a script-only cron job with `wakeAgent: false`.
9. Keep intelligence history in PostgreSQL, not in profile memory files.
10. Review audit records and failed cron runs regularly; redact secrets before
    retaining logs or opening issues.

## What the installer migrates

For each profile, the installer copies:

- `config.yaml` and `.env.example`, then creates a protected `.env` template.
- `SOUL.md`.
- `memories/`.
- `skills/`.
- `cron/jobs.json`.
- `prompts/`.
- `sessions/`, `logs/`, `gateway/`, and `audit/` placeholders.
- The maintainer's script-only `scripts/health-watchdog.sh`.

It rewrites only the copied files, never the repository source. The following
values are localized:

- `/home/$USER/code/threat-intel-agent/` → the selected repository path.
- `https://ops.cti-hermes.local` → `--private-service-url` when supplied.
- Staging profile paths → the selected runtime profile paths.

`PRIVATE_SERVICE_URL` is needed when jobs use private readiness, run-manifest,
historical-corpus, proposal, or publication-validation APIs. If those APIs are
not deployed, do not enable the corresponding scheduled jobs; use `--no-cron`
and configure a service later.

## Safe re-runs and migration from an existing setup

The installer does not delete existing directories. By default, it refuses to
replace an existing destination. To migrate an existing profile:

1. Stop its Hermes gateway and cron jobs.
2. Back up the complete existing profile home, especially `.env`, sessions,
   gateway state, and logs.
3. Run the installer with a new `--runtime-root`.
4. Compare configuration and prompts.
5. Copy only approved non-secret runtime state after review. Do not copy
   `MEMORY.md` between profiles.
6. Run `profile show`, `doctor`, and a manual job.
7. Disable the old profile only after the new profile succeeds.

The script has `--replace` for an explicitly approved replacement. It first
moves the existing destination to a timestamped sibling backup; it does not
silently remove it. Do not use `--replace` until the current profile has been
backed up.

## Verification checklist

For each profile, verify:

```sh
hermes --profile cti-analyst profile show
hermes --profile cti-analyst doctor
hermes --profile cti-maintainer profile show
hermes --profile cti-maintainer doctor
```

Confirm:

- Distinct Hermes homes, credentials, sessions, logs, gateway state, and
  memories.
- Absolute repository working directory.
- Pinned model and provider.
- Analyst toolsets exclude Docker, production secrets, direct database
  mutation, main push, merge, deployment, and secret rotation.
- Maintainer toolsets exclude main push, merge, unapproved deployment, CI or
  security-gate bypass, data deletion, migration-history rewrite, and analyst
  secret access.
- Analyst jobs return `SILENT` when no actionable change exists.
- The watchdog is script-only and does not wake an agent.
- Audit output contains no secrets.

If a command or Hermes release uses different CLI syntax, stop and consult
that release's `hermes --help`; do not guess a profile-home or permission
override. The repository manifests remain the policy reference, while the
installed Hermes CLI remains the source of truth for native profile state.
