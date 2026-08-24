# Hermes profile staging assets

This directory is a version-controlled staging copy. It is not a live Hermes
home and contains no credentials. A human installer must create two native
Hermes profiles with distinct runtime homes, then copy each profile's assets
into its matching home. Never run two Hermes processes against one home.

The profile-specific `config.yaml`, `.env.example`, `SOUL.md`, `memories`,
`skills`, `cron`, `sessions`, `logs`, `gateway`, `audit`, and `prompts`
directories are independent. Do not copy `MEMORY.md` between profiles.

## Create isolated profiles

Use the installed Hermes CLI as the source of truth for native profile state:

    hermes profile create cti-analyst --description "Public CTI analyst"
    hermes profile create cti-maintainer --description "Approval-gated CTI-Hermes maintainer"
    hermes --profile cti-analyst config set terminal.cwd /home/$USER/code/threat-intel-agent/
    hermes --profile cti-maintainer config set terminal.cwd /home/$USER/code/threat-intel-agent/

Use separate homes such as `/var/lib/hermes/cti-analyst` and
`/var/lib/hermes/cti-maintainer`, with OS permissions that prevent either
profile from reading the other's `.env`, sessions, skills, gateway state, or
logs. The analyst gets only public research and analyst-service access. The
maintainer gets repository and approved operational access, but never analyst
credentials or production secret files.

`PRIVATE_SERVICE_URL` is required by analyst prompts because the service's
private surface provides readiness, run manifests, history, proposals, and
publication validation. The repository deployment uses
`https://ops.cti-hermes.local` as its template value; replace it if the home
server uses another private DNS name or URL. It may be reachable only on the
home LAN, but it must still be authenticated and authorized.

## Install scheduled jobs

Review the profile-local `cron/jobs.json` first. It records the intended model,
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
