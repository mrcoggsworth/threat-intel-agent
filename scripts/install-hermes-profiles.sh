#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: install-hermes-profiles.sh [options]

Reconcile the repository Hermes profiles into independent runtime homes.
Existing managed files may be updated atomically; credentials, sessions, logs,
gateway state, audit history, memories, and operator-added files are preserved.

Options:
  --guided                    Ask beginner-friendly setup questions.
  --repo PATH                 Repository root (default: script's repository).
  --runtime-root PATH         Parent directory for the profile homes.
                              Default: ${HERMES_HOME:-$HOME/.hermes}/profiles
  --private-service-url URL   Maintainer operations service URL.
  --analyst-service-url URL   Analyst API service URL.
  --model NAME                Pinned model name (or HERMES_MODEL).
  --provider NAME             Pinned model provider (or HERMES_PROVIDER).
  --incident-summary TEXT     Recovery prompt context (optional).
  --no-cli                    Do not create profiles or run Hermes CLI commands.
  --no-cron                   Do not install profile cron jobs.
  --replace                   Explicitly back up and replace each profile.
  --yes                       Confirm --replace without prompting.
  --dry-run                   Print a machine-readable plan without writing.
  -h, --help                  Show this help.

The reconciler never copies repository secrets. It initializes .env only from
.env.example and never overwrites an existing .env.
EOF
}

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
hermes_root="${HERMES_HOME:-$HOME/.hermes}"
runtime_root="${HERMES_RUNTIME_ROOT:-$hermes_root/profiles}"
private_service_url="${PRIVATE_SERVICE_URL:-${HERMES_PRIVATE_SERVICE_URL:-https://ops.cti-hermes.home.arpa}}"
analyst_service_url="${HERMES_ANALYST_SERVICE_URL:-https://matrix-1.taild27e3c.ts.net:9443}"
model="${HERMES_MODEL:-}"
provider="${HERMES_PROVIDER:-}"
incident_summary="${HERMES_INCIDENT_SUMMARY:-No incident summary supplied.}"
guided=false
no_cli=false
no_cron=false
replace=false
yes=false
dry_run=false

die() { printf 'error: %s\n' "$*" >&2; exit 2; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --guided) guided=true ;;
        --repo) [ "$#" -ge 2 ] || die "--repo requires PATH"; repo=$2; shift ;;
        --runtime-root) [ "$#" -ge 2 ] || die "--runtime-root requires PATH"; runtime_root=$2; shift ;;
        --private-service-url) [ "$#" -ge 2 ] || die "--private-service-url requires URL"; private_service_url=$2; shift ;;
        --analyst-service-url) [ "$#" -ge 2 ] || die "--analyst-service-url requires URL"; analyst_service_url=$2; shift ;;
        --model) [ "$#" -ge 2 ] || die "--model requires NAME"; model=$2; shift ;;
        --provider) [ "$#" -ge 2 ] || die "--provider requires NAME"; provider=$2; shift ;;
        --incident-summary) [ "$#" -ge 2 ] || die "--incident-summary requires TEXT"; incident_summary=$2; shift ;;
        --no-cli) no_cli=true ;;
        --no-cron) no_cron=true ;;
        --replace) replace=true ;;
        --yes) yes=true ;;
        --dry-run) dry_run=true ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

if [ "$guided" = true ]; then
    printf 'Repository [%s]: ' "$repo"; IFS= read -r answer; [ -z "$answer" ] || repo=$answer
    printf 'Runtime profile root [%s]: ' "$runtime_root"; IFS= read -r answer; [ -z "$answer" ] || runtime_root=$answer
    printf 'Maintainer operations URL [%s]: ' "$private_service_url"; IFS= read -r answer; [ -z "$answer" ] || private_service_url=$answer
    printf 'Analyst API URL [%s]: ' "$analyst_service_url"; IFS= read -r answer; [ -z "$answer" ] || analyst_service_url=$answer
    printf 'Pinned model [%s]: ' "${model:-required}"; IFS= read -r answer; [ -z "$answer" ] || model=$answer
    printf 'Pinned provider [%s]: ' "${provider:-required}"; IFS= read -r answer; [ -z "$answer" ] || provider=$answer
    printf 'Create/update Hermes CLI jobs? [Y/n]: '; IFS= read -r answer
    case "${answer:-Y}" in [Nn]*) no_cli=true; no_cron=true ;; esac
fi

repo="$(cd "$repo" 2>/dev/null && pwd -P)" || die "repository path is invalid"
[ -d "$repo/.hermes/profiles/cti-analyst" ] || die "missing analyst staging profile"
[ -d "$repo/.hermes/profiles/cti-maintainer" ] || die "missing maintainer staging profile"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

native_profiles_root="$hermes_root/profiles"
if [ "$no_cli" != true ] && [ "$runtime_root" != "$native_profiles_root" ]; then
    die "--runtime-root must be $native_profiles_root when Hermes CLI actions are enabled; use --no-cli for an isolated root"
fi

if [ "$replace" = true ] && [ "$yes" != true ] && [ "$dry_run" != true ]; then
    printf 'This will back up and replace existing profile directories. Continue? [y/N]: '
    IFS= read -r answer
    case "$answer" in [Yy]*) ;; *) die "replacement not confirmed" ;; esac
fi

reconciler="$repo/scripts/reconcile-hermes-profiles.py"
reconciler_options=""
[ "$replace" = true ] && reconciler_options="$reconciler_options --replace"
[ "$dry_run" = true ] && reconciler_options="$reconciler_options --dry-run"
python3 "$reconciler" \
    --repo "$repo" \
    --runtime-root "$runtime_root" \
    --private-service-url "$private_service_url" \
    --analyst-service-url "$analyst_service_url" \
    --model "$model" \
    --provider "$provider" \
    --incident-summary "$incident_summary" \
    $reconciler_options

if [ "$dry_run" = true ] || [ "$no_cli" = true ] || [ "$no_cron" = true ]; then
    exit 0
fi

hermes_bin="$(command -v hermes || true)"
if [ -z "$hermes_bin" ]; then
    printf 'warning: Hermes CLI is not installed; profile jobs were not registered.\n' >&2
    exit 0
fi

for profile in cti-analyst cti-maintainer; do
    "$hermes_bin" --profile "$profile" config set terminal.cwd "$repo"
    HERMES_REPOSITORY="$repo" \
    HERMES_PROFILE="$profile" \
    HERMES_PROMPT_DIR="$runtime_root/$profile/prompts" \
    HERMES_MANIFEST="$runtime_root/$profile/cron/cti-hermes-jobs.manifest.json" \
    HERMES_CRON_BIN="$hermes_bin" \
    "$repo/scripts/install-hermes-jobs.sh"
done

printf 'Hermes profiles reconciled successfully.\n'
