# Hermes profile migration and installation guide

This guide turns the repository-staged Hermes assets into two independent
local profiles:

- `cti-analyst` for public CTI analysis, historical correlation, report
  validation, and controlled publication requests.
- `cti-maintainer` for repository maintenance, CI, operations, deployment
  preparation, and explicitly approved release work.

The repository copy under `.hermes/profiles/` is safe to commit and review. The
installed Hermes root is `$HOME/.hermes`, and this release stores named profiles
under `$HOME/.hermes/profiles/<name>/`. The installer writes the two CTI-Hermes
profiles directly into that native profile directory by default. It does not
merge them with the existing `threat-gpt` or `threat-intel-gemma` profiles, and it
never replaces an existing destination unless `--replace` is explicitly used.

Never run both CTI profiles against the same home, and never commit a runtime
`.env`, token, database URL, private key, session, or production log.

### Service endpoints

The home-lab analyst API is served by host Nginx at
`https://matrix-1.taild27e3c.ts.net:9443`. Nginx forwards that endpoint to the
loopback-published Hermes web container at `127.0.0.1:18000`; the Hermes
analyst profile must use the HTTPS URL, not the loopback address. The 9443
surface is allowlisted to Tailscale clients and requires `X-Analyst-Token`.

The separate operations surface remains `ops.cti-hermes.home.arpa` on the
private Nginx listener. For direct local Compose testing before Nginx and DNS
are ready, use `http://127.0.0.1:18000` for the analyst API. `/etc/hosts` maps
only names to IP addresses; ports belong in the URL.

If an endpoint changes later, update local DNS or hosts files, the Nginx
`server_name` and proxy routing, the TLS certificate name, the production
environment, and the Hermes profile URL values and prompt assets.

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
whether to create Hermes profiles and cron jobs. With the installed CLI and the
default answers, it creates the two native profiles below. Existing profiles in
the same directory are left untouched:

```text
$HOME/.hermes/profiles/
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
until its placeholders are replaced. Hermes also keeps global state such as
`config.yaml`, `skills/`, `cron/`, sessions, logs, and gateway state at the
root level; the installer changes only the two named profile directories and
profile-scoped CLI state.

### Intermediate: explicit, reviewable setup

Use explicit paths and skip actions you want to perform manually:

```sh
scripts/install-hermes-profiles.sh \
  --repo "$PWD" \
  --runtime-root "$HOME/.hermes/profiles" \
  --private-service-url "http://127.0.0.1:8000" \
  --analyst-service-url "http://127.0.0.1:8000" \
  --no-cron
```

Review the generated files before using them:

```sh
find "$HOME/.hermes/profiles" -maxdepth 3 -type f | sort
diff -u .hermes/profiles/cti-analyst/config.yaml \
  "$HOME/.hermes/profiles/cti-analyst/config.yaml"
```

If the CLI is unavailable, run the installer with `--no-cli`; it still places the
assets under `$HOME/.hermes/profiles/`, but it does not create aliases or edit
Hermes CLI metadata. After installing Hermes, register/configure the profiles
without copying the directories elsewhere:

```sh
hermes profile describe cti-analyst --text "Public CTI analyst"
hermes profile describe cti-maintainer \
  --text "Approval-gated CTI-Hermes maintainer"
hermes --profile cti-analyst config set terminal.cwd "$PWD"
hermes --profile cti-maintainer config set terminal.cwd "$PWD"
```

For a custom Hermes root, set `HERMES_HOME` to the parent directory before
running the installer, for example `HERMES_HOME=/var/lib/hermes`; the profile
root is then `/var/lib/hermes/profiles`. If you intentionally use a directory
that is not the native profile root, use `--no-cli` and perform the native CLI
registration separately. Do not merge the two directories or copy either
`memories/MEMORY.md` into the other profile.

Install cron jobs separately after review:

```sh
HERMES_REPOSITORY="$PWD" \
HERMES_PROFILE=cti-analyst \
HERMES_PROMPT_DIR="$HOME/.hermes/profiles/cti-analyst/prompts" \
scripts/install-hermes-jobs.sh

HERMES_REPOSITORY="$PWD" \
HERMES_PROFILE=cti-maintainer \
HERMES_PROMPT_DIR="$HOME/.hermes/profiles/cti-maintainer/prompts" \
scripts/install-hermes-jobs.sh
```

### Advanced: service-account and host isolation

For a home server or multi-user host:

1. Create two OS service accounts or two locked-down service identities.
2. Give each identity ownership of only its Hermes home, for example
   `/var/lib/hermes/profiles/cti-analyst` and `/var/lib/hermes/profiles/cti-maintainer`.
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

The installed Hermes root remains the owner of global state such as `config.yaml`,
`cron/`, `skills/`, gateway state, and top-level sessions/logs. The installer
adds only `cti-analyst/` and `cti-maintainer/` below the native profile root; it
does not copy or merge the existing `threat-gpt` or `threat-intel-gemma` homes.

For each profile, the installer copies:

- `config.yaml` and `.env.example`, then creates a protected `.env` template.
- `SOUL.md`.
- `memories/`.
- `skills/`.
- `cron/cti-hermes-jobs.manifest.json`.
- `prompts/`.
- `sessions/`, `logs/`, `gateway/`, and `audit/` placeholders.
- The maintainer's script-only `scripts/health-watchdog.sh`.

It rewrites only the copied files, never the repository source. The following
values are localized:

- `/home/$USER/code/threat-intel-agent/` → the selected repository path.
- `https://ops.cti-hermes.home.arpa` → `--private-service-url` when supplied.
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
