# Hermes profile installation

These instructions use two separate Hermes homes. Replace every bracketed
placeholder with a verified local value; do not put credentials in this
repository or in prompt files.

## Create isolated profiles

The profile CLI is the source of truth for profile and cron state. Do not edit
jobs.json directly.

    hermes profile create cti-analyst --description "Public CTI analyst"
    hermes profile create cti-maintainer --description "CTI-Hermes maintainer"
    hermes --profile cti-analyst config set terminal.cwd /ABSOLUTE/REPOSITORY
    hermes --profile cti-maintainer config set terminal.cwd /ABSOLUTE/REPOSITORY

Set distinct homes, for example /var/lib/hermes/cti-analyst and
/var/lib/hermes/cti-maintainer, with permissions that prevent either profile
from reading the other's .env, sessions, skills, gateway state, or logs. The
analyst profile receives only public research access and the CTI service analyst
token. The maintainer profile receives repository and approved operational
access, but never the analyst token or production secret files.

## Install scheduled jobs

Run scripts/install-hermes-jobs.sh once per profile after replacing the
placeholders in its environment. It invokes the supported Hermes cron command
and never edits the cron database directly.

    HERMES_REPOSITORY=/ABSOLUTE/REPOSITORY \
    HERMES_ANALYST_SERVICE_URL=https://ops.cti-hermes.local \
    scripts/install-hermes-jobs.sh

The script installs daily analyst and feed-quality jobs, weekly historical
resurfacing and maintenance jobs, monthly retrospective, approved-release,
recovery, and script-only health-watchdog instructions. Review each job and
manually trigger it before enabling recurrence. Health success is silent.
Cron prompts are self-contained and use the absolute workdir.

No profile is authorized to merge, push main, weaken CI, expose private routes,
rewrite migrations, delete data, or deploy without the required human approval.
The analyst profile cannot run maintainer operations.
