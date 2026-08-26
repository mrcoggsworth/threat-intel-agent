#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: install-hermes-profiles.sh [options]

Prepare two isolated Hermes profile homes from .hermes/profiles/.

By default the homes are installed as native Hermes profiles under
${HERMES_HOME:-$HOME/.hermes}/profiles/. Existing profiles are never replaced
unless --replace is explicitly supplied.
Options:
  --guided                    Ask beginner-friendly setup questions.
  --repo PATH                 Repository root (default: script's repository).
  --runtime-root PATH         Parent directory for the two profile homes.
                              Default: ${HERMES_HOME:-$HOME/.hermes}/profiles
                              With Hermes CLI actions enabled, this must be the
                              native profiles directory for that Hermes root.
  --private-service-url URL   Maintainer operations service URL.
  --analyst-service-url URL   Analyst API service URL.
  --no-cli                    Do not create profiles or run Hermes CLI commands.
  --no-cron                   Do not install profile cron jobs.
  --replace                   Back up existing destinations before replacing.
  --yes                       Accept non-destructive confirmations.
  --dry-run                   Print planned actions without changing files.
  -h, --help                  Show this help.

The script never copies secrets from the repository. It creates runtime .env
files only from .env.example templates and never overwrites an existing .env.
EOF
}

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
hermes_root="${HERMES_HOME:-$HOME/.hermes}"
runtime_root="${HERMES_RUNTIME_ROOT:-$hermes_root/profiles}"
private_service_url="${PRIVATE_SERVICE_URL:-${HERMES_PRIVATE_SERVICE_URL:-https://ops.cti-hermes.home.arpa}}"
analyst_service_url="${HERMES_ANALYST_SERVICE_URL:-https://matrix-1.taild27e3c.ts.net:9443}"
guided=false
no_cli=false
no_cron=false
replace=false
yes=false
dry_run=false

say() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 2; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --guided) guided=true ;;
        --repo) [ "$#" -ge 2 ] || die "--repo requires PATH"; repo=$2; shift ;;
        --runtime-root) [ "$#" -ge 2 ] || die "--runtime-root requires PATH"; runtime_root=$2; shift ;;
        --private-service-url) [ "$#" -ge 2 ] || die "--private-service-url requires URL"; private_service_url=$2; shift ;;
        --analyst-service-url) [ "$#" -ge 2 ] || die "--analyst-service-url requires URL"; analyst_service_url=$2; shift ;;
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
    printf 'Repository [%s]: ' "$repo"
    IFS= read -r answer
    [ -z "$answer" ] || repo=$answer
    printf 'Runtime profile root [%s]: ' "$runtime_root"
    IFS= read -r answer
    [ -z "$answer" ] || runtime_root=$answer
    printf 'Maintainer operations URL [%s]: ' "$private_service_url"
    IFS= read -r answer
    [ -z "$answer" ] || private_service_url=$answer
    printf 'Analyst API URL [%s]: ' "$analyst_service_url"
    IFS= read -r answer
    [ -z "$answer" ] || analyst_service_url=$answer
    printf 'Create Hermes profiles and install cron jobs? [Y/n]: '
    IFS= read -r answer
    case "${answer:-Y}" in
        [Nn]*) no_cli=true; no_cron=true ;;
    esac
fi

repo="$(cd "$repo" 2>/dev/null && pwd -P)" || die "repository path is invalid"
stage_root="$repo/.hermes/profiles"
[ -d "$stage_root/cti-analyst" ] || die "missing analyst staging profile: $stage_root/cti-analyst"
[ -d "$stage_root/cti-maintainer" ] || die "missing maintainer staging profile: $stage_root/cti-maintainer"
command -v python3 >/dev/null 2>&1 || die "python3 is required for safe path localization"

if [ "$dry_run" = true ]; then
    runtime_root="${runtime_root%/}"
else
    runtime_root="$(mkdir -p "$runtime_root" && cd "$runtime_root" && pwd -P)"
fi

native_profiles_root="$hermes_root/profiles"
if [ "$no_cli" != true ] && [ "$runtime_root" != "$native_profiles_root" ]; then
    die "--runtime-root must be $native_profiles_root when Hermes CLI actions are enabled; set HERMES_HOME to the parent Hermes root or use --no-cli"
fi

hermes_bin=""
if [ "$no_cli" = true ]; then
    say "Hermes CLI actions skipped by request."
else
    hermes_bin="$(command -v hermes || true)"
    if [ -z "$hermes_bin" ]; then
        warn "Hermes CLI is not installed; profile creation and cron installation will be skipped."
        no_cli=true
    fi
fi

profiles=(cti-analyst cti-maintainer)

if [ "$replace" = true ] && [ "$yes" != true ] && [ "$dry_run" != true ]; then
    printf 'This will back up and replace existing profile directories. Continue? [y/N]: '
    IFS= read -r answer
    case "$answer" in [Yy]*) ;; *) die "replacement not confirmed" ;; esac
fi

run_or_print() {
    if [ "$dry_run" = true ]; then
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
    else
        "$@"
    fi
}

localize_profile() {
    local profile=$1
    local destination=$2
    local service_url="$private_service_url"
    [ "$profile" = cti-analyst ] && service_url="$analyst_service_url"
    python3 - "$destination" "$repo" "$service_url" "$destination" "$profile" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
repo = sys.argv[2].rstrip("/") + "/"
service_url = sys.argv[3].rstrip("/")
destination = sys.argv[4]
profile = sys.argv[5]
source_profile = repo.rstrip("/") + f"/.hermes/profiles/{profile}"
source_literal = f"/home/$USER/code/threat-intel-agent/.hermes/profiles/{profile}"
relative_profile = f".hermes/profiles/{profile}/"
sentinel = "__HERMES_PROFILE_DESTINATION__"

for path in root.rglob("*"):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    text = text.replace(source_profile, sentinel)
    text = text.replace(source_literal, sentinel)
    text = text.replace(relative_profile, sentinel)
    text = text.replace("/home/$USER/code/threat-intel-agent/", repo)
    text = text.replace("https://ops.cti-hermes.home.arpa", service_url)
    text = text.replace("https://matrix-1.taild27e3c.ts.net:9443", service_url)
    text = text.replace(sentinel, destination)
    path.write_text(text, encoding="utf-8")
PY
}

for profile in "${profiles[@]}"; do
    source="$stage_root/$profile"
    destination="$runtime_root/$profile"
    say "Preparing $profile -> $destination"
    if [ -e "$destination" ]; then
        if [ "$replace" = true ]; then
            backup="$runtime_root/${profile}.backup.$(date -u +%Y%m%dT%H%M%SZ)"
            run_or_print mv "$destination" "$backup"
            say "  Existing home backed up at $backup"
        else
            die "$destination already exists; choose another --runtime-root or use --replace"
        fi
    fi
    if [ "$dry_run" != true ] && [ "$no_cli" != true ]; then
        description="Public CTI analyst"
        [ "$profile" = cti-maintainer ] && description="Approval-gated CTI-Hermes maintainer"
        "$hermes_bin" profile create "$profile" --no-alias --no-skills --description "$description"
    fi
    runtime_jobs_backup=""
    if [ "$dry_run" != true ] && [ -f "$destination/cron/jobs.json" ]; then
        runtime_jobs_backup="$destination/cron/.hermes-jobs.json.bootstrap"
        mv "$destination/cron/jobs.json" "$runtime_jobs_backup"
    fi
    run_or_print mkdir -p "$destination"
    run_or_print cp -R "$source/." "$destination/"
    if [ "$dry_run" != true ]; then
        if [ -f "$destination/cron/jobs.json" ]; then
            mv "$destination/cron/jobs.json" "$destination/cron/cti-hermes-jobs.manifest.json"
        fi
        if [ -n "$runtime_jobs_backup" ]; then
            mv "$runtime_jobs_backup" "$destination/cron/jobs.json"
        fi
    fi
    if [ "$dry_run" != true ]; then
        localize_profile "$profile" "$destination"
        if [ ! -e "$destination/.env" ] || [ ! -s "$destination/.env" ]; then
            cp "$destination/.env.example" "$destination/.env"
            chmod 0600 "$destination/.env"
        fi
        chmod 0700 "$destination" "$destination/sessions" "$destination/logs" "$destination/gateway" "$destination/audit"
    fi
done

if [ "$dry_run" = true ]; then
    say "Dry run complete; no files or Hermes state changed."
    exit 0
fi

if [ "$no_cli" != true ]; then
    for profile in "${profiles[@]}"; do
        "$hermes_bin" --profile "$profile" config set terminal.cwd "$repo"
    done
fi

if [ "$no_cron" = true ]; then
    say "Cron installation skipped by request."
elif [ "$no_cli" = true ]; then
    say "Cron installation skipped because Hermes CLI is unavailable."
else
    for profile in "${profiles[@]}"; do
        HERMES_REPOSITORY="$repo" \
        HERMES_PROFILE="$profile" \
        HERMES_PROMPT_DIR="$runtime_root/$profile/prompts" \
        HERMES_CRON_BIN="$hermes_bin" \
        "$repo/scripts/install-hermes-jobs.sh"
    done
fi

say "Profile assets prepared successfully."
say "Edit: $runtime_root/cti-analyst/.env"
say "Edit: $runtime_root/cti-maintainer/.env"
say "Do not enable recurrence until profile show, doctor, and manual job checks pass."
