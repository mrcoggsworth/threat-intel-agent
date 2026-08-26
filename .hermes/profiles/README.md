# Hermes profile staging assets

This directory is a version-controlled staging copy. It is not a live Hermes
home and contains no credentials. The installer places its two profiles under
`$HOME/.hermes/profiles/` (or `$HERMES_HOME/profiles/` for a custom root),
which is the native layout for the installed Hermes CLI. Never run two Hermes
processes against one home.

The profile-specific `config.yaml`, `.env.example`, `SOUL.md`, `memories`,
`skills`, `cron`, `sessions`, `logs`, `gateway`, `audit`, and `prompts`
directories are independent. Do not copy `MEMORY.md` between profiles.

## Create isolated profiles

Run `scripts/install-hermes-profiles.sh --guided` from the repository root. With
the Hermes CLI installed, it creates the native profiles, sets their repository
working directory, and can install the profile cron jobs. It refuses to replace
existing destinations, including any existing named profiles.

If the CLI is unavailable, use `--no-cli`; the assets are still placed under the
native profile root. Once Hermes is installed, set metadata and the working
directory with:

    hermes profile describe cti-analyst --text "Public CTI analyst"
    hermes profile describe cti-maintainer --text "Approval-gated CTI-Hermes maintainer"
    hermes --profile cti-analyst config set terminal.cwd /home/$USER/code/threat-intel-agent/
    hermes --profile cti-maintainer config set terminal.cwd /home/$USER/code/threat-intel-agent/

For a custom installation, set `HERMES_HOME` to the parent root, for example
`/var/lib/hermes`; the native profile path is then `/var/lib/hermes/profiles/`.
Use separate homes with OS permissions that prevent either profile from reading
the other profile .env, sessions, skills, gateway state, or logs.

The current private service name is `ops.cti-hermes.home.arpa`; it must resolve through local DNS or `/etc/hosts`. It is not a public DNS name and is not automatically available.

`PRIVATE_SERVICE_URL` is required by analyst prompts because the service's
private surface provides readiness, run manifests, history, proposals, and
publication validation. The repository deployment uses
`https://ops.cti-hermes.home.arpa` as its template value; replace it if the home
server uses another private DNS name or URL. It may be reachable only on the
home LAN, but it must still be authenticated and authorized.

## Install scheduled jobs

Review the profile-local `cron/cti-hermes-jobs.manifest.json` first. It records the intended model,
provider, preflight, toolset, absolute workdir, wake behavior, and prompt file.
Then install one profile at a time through the supported CLI:

    HERMES_REPOSITORY=/home/$USER/code/threat-intel-agent/ \
    HERMES_PROFILE=cti-analyst \
    scripts/install-hermes-jobs.sh

Repeat with `HERMES_PROFILE=cti-maintainer`. The health watchdog is a script-only
no-agent job with `wakeAgent: false`; successful checks are silent. Manually
trigger every job, verify failure history and output, then enable recurrence.
Cron prompts are self-contained and must not create cron jobs.

## Verification checklist

For each profile run `profile show` and `doctor`; verify native home, absolute
working directory, pinned model/provider, distinct credentials, gateway
identity, toolsets, and cron list. Confirm analyst deny rules prevent Docker,
production secrets, direct database mutation, main push, merge, and deployment.
Confirm maintainer deny rules prevent main push, merge, unapproved deployment,
security-gate bypass, data deletion, migration-history rewrite, and analyst
secret access. Keep audit records secret-free.

The generated profile cron manifest is retained as `cron/jobs.json` for CLI compatibility.
