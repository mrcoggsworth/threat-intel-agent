#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: install-hermes-profiles.sh [options]

Prepare two isolated Hermes profile homes from .hermes/profiles/.

Options:
  --guided                    Ask beginner-friendly setup questions.
  --repo PATH                 Repository root (default: script's repository).
  --runtime-root PATH         Parent directory for the two profile homes.
                              Default: $HOME/.hermes-profiles
  --private-service-url URL   Private CTI service URL.
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
runtime_root="${HERMES_RUNTIME_ROOT:-$HOME/.hermes-profiles}"
private_service_url="${PRIVATE_SERVICE_URL:-${HERMES_PRIVATE_SERVICE_URL:-https://ops.cti-hermes.local}}"
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
    printf 'Private service URL [%s]: ' "$private_service_url"
    IFS= read -r answer
    [ -z "$answer" ] || private_service_url=$answer
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

if [ $dry_run = true ]; then
    runtime_root="${runtime_root%/}"
else
    runtime_root="$(mkdir -p "$runtime_root" && cd "$runtime_root" && pwd -P)"
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
    python3 - "$destination" "$repo" "$private_service_url" "$destination" "$profile" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
repo = sys.argv[2].rstrip("/") + "/"
service_url = sys.argv[3].rstrip("/")
destination = sys.argv[4]
profile = sys.argv[5]

replacements = {
    f"/home/$USER/code/threat-intel-agent/.hermes/profiles/{profile}": destination,
    f".hermes/profiles/{profile}/": destination.rstrip("/") + "/",
    "/home/$USER/code/threat-intel-agent/": repo,
    "https://ops.cti-hermes.local": service_url,
}

for path in root.rglob("*"):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for old, new in replacements.items():
        text = text.replace(old, new)
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
    run_or_print mkdir -p "$destination"
    run_or_print cp -R "$source/." "$destination/"
    if [ "$dry_run" != true ]; then
        localize_profile "$profile" "$destination"
        if [ ! -e "$destination/.env" ]; then
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

hermes_bin="$(command -v hermes || true)"
if [ "$no_cli" = true ]; then
    say "Hermes CLI actions skipped by request."
elif [ -z "$hermes_bin" ]; then
    warn "Hermes CLI is not installed; profile creation and cron installation were skipped."
    no_cli=true
else
    for profile in "${profiles[@]}"; do
        description="Public CTI analyst"
        [ "$profile" = cti-maintainer ] && description="Approval-gated CTI-Hermes maintainer"
        if ! "$hermes_bin" profile create "$profile" --description "$description"; then
            warn "$profile may already exist; continuing to configure its working directory"
        fi
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
