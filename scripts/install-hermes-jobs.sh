#!/bin/sh
set -eu

# The profile CLI remains the execution backend; the repository manifest is
# the policy source for every installed field. Existing same-name jobs are
# removed only when this reconciler previously recorded ownership. The older
# `cron add` workflow is intentionally represented by `cron create` here.

repo=${HERMES_REPOSITORY:?HERMES_REPOSITORY is required}
profile=${HERMES_PROFILE:?HERMES_PROFILE is required (cti-analyst or cti-maintainer)}
cron_bin=${HERMES_CRON_BIN:-hermes}
manifest=${HERMES_MANIFEST:-${HERMES_PROMPT_DIR:-$repo/.hermes/profiles/$profile/prompts}/../cron/cti-hermes-jobs.manifest.json}

case "$profile" in
    cti-analyst|cti-maintainer) ;;
    *) echo "unsupported Hermes profile: $profile" >&2; exit 2 ;;
esac

[ -f "$manifest" ] || { echo "job manifest is missing: $manifest" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 2; }

python3 - "$repo" "$profile" "$manifest" "$cron_bin" <<'PY'
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


repo = Path(sys.argv[1]).resolve()
profile = sys.argv[2]
manifest_path = Path(sys.argv[3]).resolve()
cron_bin = sys.argv[4]
runtime_profile = manifest_path.parent.parent
ownership_path = runtime_profile / ".hermes-reconciler" / "job-ownership.json"

try:
    jobs = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"invalid job manifest: {manifest_path}: {exc}") from exc
if not isinstance(jobs, list):
    raise SystemExit("job manifest must contain a list")

try:
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    ownership = {}
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"invalid job ownership record: {ownership_path}: {exc}") from exc
if not isinstance(ownership, dict):
    raise SystemExit("job ownership record must be an object")

listed = subprocess.run(
    [cron_bin, "--profile", profile, "cron", "list"],
    check=False,
    capture_output=True,
    text=True,
)
listing = listed.stdout + "\n" + listed.stderr
names: dict[str, str] = {}
last_id = ""
for line in listing.splitlines():
    match_id = re.match(r"\s*([A-Za-z0-9_-]+).*", line)
    if match_id and line.strip().startswith(match_id.group(1)):
        last_id = match_id.group(1)
    match_name = re.search(r"Name:\s*(\S+)", line)
    if match_name and last_id:
        names[match_name.group(1)] = last_id


def flag_value(
    job: dict[str, Any], key: str, true_flag: str, false_flag: str
) -> list[str]:
    if key not in job:
        return []
    return [true_flag if bool(job[key]) else false_flag]


new_ownership: dict[str, str] = {}
for raw_job in jobs:
    if not isinstance(raw_job, dict):
        raise SystemExit("each job manifest entry must be an object")
    job = raw_job
    job_id = str(job.get("id", ""))
    if not job_id or str(job.get("profile", profile)) != profile:
        raise SystemExit(f"job has invalid id or profile: {job_id}")
    required = ("schedule", "workdir", "wakeAgent")
    missing = [key for key in required if key not in job]
    if missing:
        raise SystemExit(f"job {job_id} is missing: {', '.join(missing)}")
    workdir = Path(str(job["workdir"]))
    if not workdir.is_absolute() or workdir.resolve() != repo:
        raise SystemExit(f"job {job_id} has unsafe workdir: {workdir}")

    existing_id = names.get(job_id)
    owned_id = str(ownership.get(job_id, ""))
    if existing_id and existing_id != owned_id:
        raise SystemExit(
            f"unmanaged conflicting cron job {job_id}; review it before replacing"
        )
    if existing_id:
        subprocess.run(
            [cron_bin, "--profile", profile, "cron", "remove", existing_id],
            check=True,
        )

    command = [
        cron_bin,
        "--profile",
        profile,
        "cron",
        "create",
        str(job["schedule"]),
    ]
    prompt_file = job.get("prompt_file")
    if prompt_file:
        prompt_path = Path(str(prompt_file))
        prompt = str(job.get("prompt", ""))
        if not prompt:
            prompt = prompt_path.read_text(encoding="utf-8")
        command.append(prompt)
    elif job.get("command"):
        command.extend(["--script", str(job["command"])])
    else:
        raise SystemExit(f"job {job_id} has neither prompt_file nor command")
    command.extend(["--name", job_id, "--workdir", str(workdir)])
    for key, option in (
        ("model", "--model"),
        ("provider", "--provider"),
        ("preflight", "--preflight"),
        ("monitor", "--monitor"),
    ):
        if job.get(key) is not None:
            command.extend([option, str(job[key])])
    for toolset in job.get("toolsets", []):
        command.extend(["--toolset", str(toolset)])
    command.extend(flag_value(job, "wakeAgent", "--wake-agent", "--no-wake-agent"))
    command.extend(
        flag_value(
            job,
            "wakeAgentWhenPreflightEmpty",
            "--wake-agent-when-preflight-empty",
            "--no-wake-agent-when-preflight-empty",
        )
    )
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    refreshed = subprocess.run(
        [cron_bin, "--profile", profile, "cron", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    refreshed_id = ""
    last_refreshed_id = ""
    for line in (refreshed.stdout + "\n" + refreshed.stderr).splitlines():
        match_id = re.match(r"\s*([A-Za-z0-9_-]+).*", line)
        if match_id and line.strip().startswith(match_id.group(1)):
            last_refreshed_id = match_id.group(1)
        match_name = re.search(r"Name:\s*(\S+)", line)
        if match_name and match_name.group(1) == job_id:
            refreshed_id = last_refreshed_id
            break
    matches = re.findall(r"\b([A-Za-z0-9_-]{6,})\b", completed.stdout)
    new_ownership[job_id] = refreshed_id or (matches[-1] if matches else job_id)

ownership_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
temporary = ownership_path.with_name(f".{ownership_path.name}.tmp")
temporary.write_text(
    json.dumps(new_ownership, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
os.chmod(temporary, 0o600)
os.replace(temporary, ownership_path)
print(f"Hermes cron definitions reconciled for {profile}")
PY
