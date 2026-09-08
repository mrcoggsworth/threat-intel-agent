#!/usr/bin/env python3
"""Safely reconcile repository Hermes profiles into runtime profile homes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROFILES = ("cti-analyst", "cti-maintainer")
METADATA_DIR = ".hermes-reconciler"
MANIFEST_NAME = "managed-manifest.json"
PLACEHOLDER_PATTERN = re.compile(r"(?:\$USER|\$\{USER\}|__[^\n]*__|/home/\$USER/)")
PROTECTED_PREFIXES = ("sessions/", "logs/", "gateway/", "memories/")
PROTECTED_FILES = {".env", "audit/events.jsonl"}


class ReconciliationError(RuntimeError):
    """Raised when a profile cannot be reconciled safely."""


@dataclass(frozen=True)
class Inputs:
    repo: Path
    runtime_root: Path
    private_service_url: str
    analyst_service_url: str
    model: str
    provider: str
    incident_summary: str
    dry_run: bool
    replace: bool


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ReconciliationError(f"path escapes selected root: {path}") from exc


def ensure_safe_path(path: Path, root: Path) -> None:
    """Reject a symlinked path component that could escape the profile root."""

    root = root.resolve()
    try:
        relative_path(path, root)
    except ReconciliationError:
        raise
    current = root
    for component in path.relative_to(root).parts:
        current /= component
        if not current.is_symlink():
            continue
        target = current.resolve(strict=False)
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ReconciliationError(
                f"refusing symlink outside profile root: {current} -> {target}"
            ) from exc


def validate_url(name: str, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ReconciliationError(f"{name} must be an absolute HTTP(S) URL")
    if PLACEHOLDER_PATTERN.search(value):
        raise ReconciliationError(f"{name} contains an unresolved placeholder")
    return value.rstrip("/")


def validate_setting(name: str, value: str) -> str:
    value = value.strip()
    if not value or PLACEHOLDER_PATTERN.search(value):
        raise ReconciliationError(f"{name} must be resolved before installation")
    return value


def is_protected(path: str) -> bool:
    return path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)


def mode_for(path: Path, source: Path) -> int:
    if path.exists() and not path.is_symlink():
        return stat.S_IMODE(path.stat().st_mode)
    return stat.S_IMODE(source.stat().st_mode) or 0o600


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def render_bytes(
    source: Path, inputs: Inputs, profile: str, destination: Path
) -> bytes:
    try:
        rendered = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return source.read_bytes()
    source_profile = inputs.repo / ".hermes" / "profiles" / profile
    replacements = (
        (str(source_profile), str(destination)),
        (
            f"/home/$USER/code/threat-intel-agent/.hermes/profiles/{profile}",
            str(destination),
        ),
        (f".hermes/profiles/{profile}/", f"{destination.as_posix()}/"),
        ("/home/$USER/code/threat-intel-agent/", f"{inputs.repo.as_posix()}/"),
        ("https://ops.cti-hermes.home.arpa", inputs.private_service_url),
        ("https://matrix-1.taild27e3c.ts.net:9443", inputs.analyst_service_url),
        ("__SET_AND_PIN_MODEL__", inputs.model),
        ("__SET_AND_PIN_PROVIDER__", inputs.provider),
        ("__INCIDENT_SUMMARY__", inputs.incident_summary),
        (
            "__REQUIRED_APPROVED_RELEASE__",
            "explicit approved immutable release reference",
        ),
        ("__EVENT_ID__", "event id supplied by preflight"),
        ("__RUN_IDS__", "run ids supplied by preflight"),
        ("__SOURCE_ID__", "source id supplied by preflight"),
        ("__REQUIRED_PER_APPROVED_OPERATION__", "explicit approval reference"),
    )
    for old, new in replacements:
        rendered = rendered.replace(old, new)
    return rendered.encode("utf-8")


def validate_materialized(path: str, data: bytes, inputs: Inputs) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    if PLACEHOLDER_PATTERN.search(text):
        raise ReconciliationError(f"{path} contains an unresolved placeholder")
    if str(inputs.repo) in text and "/.hermes/profiles/" in text:
        raise ReconciliationError(f"{path} retains a staging profile path")


def backup_existing(path: Path, profile_root: Path, backup_root: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    destination = backup_root / relative_path(path, profile_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        destination.write_text(os.readlink(path), encoding="utf-8")
    else:
        shutil.copy2(path, destination)


def load_jobs(
    source: Path, inputs: Inputs, profile: str, destination: Path
) -> list[dict[str, Any]]:
    manifest_path = source / "cron" / "cti-hermes-jobs.manifest.json"
    try:
        jobs = json.loads(
            render_bytes(manifest_path, inputs, profile, destination).decode("utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationError(f"invalid job manifest: {manifest_path}") from exc
    if not isinstance(jobs, list):
        raise ReconciliationError("job manifest must contain a list")
    resolved: list[dict[str, Any]] = []
    for raw_job in jobs:
        if not isinstance(raw_job, dict):
            raise ReconciliationError("each job manifest entry must be an object")
        job = dict(raw_job)
        job["profile"] = profile
        job["workdir"] = str(inputs.repo)
        prompt_file = job.get("prompt_file")
        if prompt_file is not None:
            prompt_name = Path(str(prompt_file)).name
            prompt_path = source / "prompts" / prompt_name
            if not prompt_path.is_file():
                raise ReconciliationError(f"job prompt is missing: {prompt_path}")
            job["prompt_file"] = str(destination / "prompts" / prompt_name)
            job["prompt"] = render_bytes(
                prompt_path, inputs, profile, destination / "prompts" / prompt_name
            ).decode("utf-8")
        command = job.get("command")
        if command is not None:
            job["command"] = str(destination / "scripts" / Path(str(command)).name)
        resolved.append(job)
    return resolved


def action_for(existing: bytes | None, desired: bytes) -> str:
    if existing is None:
        return "created"
    if existing == desired:
        return "unchanged"
    return "updated"


def reconcile_profile(inputs: Inputs, profile: str) -> dict[str, Any]:
    source_root = inputs.repo / ".hermes" / "profiles" / profile
    destination_root = inputs.runtime_root / profile
    if not source_root.is_dir():
        raise ReconciliationError(f"missing staging profile: {source_root}")
    destination_root = destination_root.absolute()
    ensure_safe_path(destination_root, inputs.runtime_root.absolute())
    if destination_root.is_symlink():
        if inputs.replace:
            raise ReconciliationError("--replace cannot target a symlinked profile")
        ensure_safe_path(destination_root, inputs.runtime_root.absolute())
    if inputs.replace and destination_root.exists() and not inputs.dry_run:
        backup = inputs.runtime_root / (
            f"{profile}.replacement-backup.{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
        )
        if backup.exists():
            raise ReconciliationError(f"replacement backup already exists: {backup}")
        shutil.copytree(destination_root, backup, symlinks=True)
        shutil.rmtree(destination_root)
    if not inputs.dry_run:
        destination_root.mkdir(parents=True, exist_ok=True)
        os.chmod(destination_root, 0o700)

    backup_root = destination_root / METADATA_DIR / "backups" / timestamp()
    report_assets: list[dict[str, Any]] = []
    managed: dict[str, dict[str, str]] = {}
    source_files = sorted(path for path in source_root.rglob("*") if path.is_file())
    source_relatives = {relative_path(path, source_root) for path in source_files}
    for source in source_files:
        ensure_safe_path(source, source_root)
        rel = relative_path(source, source_root)
        destination = destination_root / rel
        ensure_safe_path(destination, destination_root)
        desired = render_bytes(source, inputs, profile, destination_root)
        if rel == "cron/jobs.json":
            jobs = load_jobs(source_root, inputs, profile, destination_root)
            desired = (json.dumps(jobs, indent=2) + "\n").encode("utf-8")
        validate_materialized(rel, desired, inputs)
        if (
            destination.exists()
            and not destination.is_file()
            and not destination.is_symlink()
        ):
            raise ReconciliationError(f"managed asset is not a file: {destination}")
        existing = destination.read_bytes() if destination.is_file() else None
        protected = is_protected(rel)
        action = (
            "preserved"
            if protected and existing is not None
            else action_for(existing, desired)
        )
        if protected and existing is None:
            action = "created"
        if not inputs.dry_run and action in {"created", "updated"}:
            if action == "updated":
                backup_existing(destination, destination_root, backup_root)
            atomic_write(destination, desired, mode_for(destination, source))
        record = {
            "path": rel,
            "owner": "protected" if protected else "managed",
            "action": action,
            "source_hash": sha256_bytes(desired),
            "destination_hash": sha256_bytes(
                desired
                if action in {"created", "updated", "unchanged"}
                else existing or b""
            ),
        }
        report_assets.append(record)
        if not protected:
            managed[rel] = {
                "source_hash": record["source_hash"],
                "destination_hash": record["destination_hash"],
                "owner": "managed",
                "timestamp": timestamp(),
            }

    env_source = source_root / ".env.example"
    env_destination = destination_root / ".env"
    ensure_safe_path(env_destination, destination_root)
    env_desired = render_bytes(env_source, inputs, profile, destination_root)
    validate_materialized(".env", env_desired, inputs)
    if (
        env_destination.exists()
        and not env_destination.is_file()
        and not env_destination.is_symlink()
    ):
        raise ReconciliationError(f"protected asset is not a file: {env_destination}")
    env_existing = env_destination.read_bytes() if env_destination.is_file() else None
    env_action = "preserved" if env_existing is not None else "created"
    if not inputs.dry_run and env_existing is None:
        atomic_write(env_destination, env_desired, 0o600)
    report_assets.append(
        {
            "path": ".env",
            "owner": "protected",
            "action": env_action,
            "source_hash": sha256_bytes(env_desired),
            "destination_hash": sha256_bytes(env_existing or env_desired),
        }
    )
    source_relatives.add(".env")

    if inputs.dry_run and destination_root.exists():
        for candidate in destination_root.rglob("*"):
            if candidate.is_symlink():
                ensure_safe_path(candidate, destination_root)
        unknown = sorted(
            path
            for path in destination_root.rglob("*")
            if path.is_file()
            and relative_path(path, destination_root) not in source_relatives
            and not relative_path(path, destination_root).startswith(f"{METADATA_DIR}/")
        )
        for path in unknown:
            report_assets.append(
                {
                    "path": relative_path(path, destination_root),
                    "owner": "operator",
                    "action": "preserved",
                    "source_hash": "",
                    "destination_hash": sha256_bytes(path.read_bytes()),
                }
            )

    if not inputs.dry_run:
        for directory in sorted({path.parent for path in source_files}):
            rel_dir = relative_path(directory, source_root)
            target_dir = destination_root / rel_dir
            ensure_safe_path(target_dir, destination_root)
            target_dir.mkdir(parents=True, exist_ok=True)
            if rel_dir in {"sessions", "logs", "gateway", "audit", "memories"}:
                os.chmod(target_dir, 0o700)

        for candidate in destination_root.rglob("*"):
            if candidate.is_symlink():
                ensure_safe_path(candidate, destination_root)

        unknown = sorted(
            path
            for path in destination_root.rglob("*")
            if path.is_file()
            and relative_path(path, destination_root) not in source_relatives
            and not relative_path(path, destination_root).startswith(f"{METADATA_DIR}/")
        )
        for path in unknown:
            rel = relative_path(path, destination_root)
            report_assets.append(
                {
                    "path": rel,
                    "owner": "operator",
                    "action": "preserved",
                    "source_hash": "",
                    "destination_hash": sha256_bytes(path.read_bytes()),
                }
            )

        metadata = destination_root / METADATA_DIR
        metadata.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(metadata, 0o700)
        previous_manifest = metadata / MANIFEST_NAME
        if previous_manifest.exists():
            backup_existing(previous_manifest, destination_root, backup_root)
        manifest = {
            "schema_version": 1,
            "profile": profile,
            "generated_at": timestamp(),
            "managed_assets": managed,
            "protected_patterns": [*PROTECTED_PREFIXES, *sorted(PROTECTED_FILES)],
        }
        atomic_write(
            previous_manifest,
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            0o600,
        )
    summary = {
        action: 0
        for action in (
            "created",
            "updated",
            "unchanged",
            "preserved",
            "skipped",
            "blocked",
        )
    }
    for asset in report_assets:
        summary[str(asset["action"])] += 1
    return {
        "profile": profile,
        "destination": str(destination_root),
        "assets": sorted(report_assets, key=lambda item: str(item["path"])),
        "summary": summary,
        "backup": None
        if inputs.dry_run or not backup_root.exists()
        else str(backup_root),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo", type=Path, required=True)
    result.add_argument("--runtime-root", type=Path, required=True)
    result.add_argument("--private-service-url", required=True)
    result.add_argument("--analyst-service-url", required=True)
    result.add_argument("--model", required=True)
    result.add_argument("--provider", required=True)
    result.add_argument("--incident-summary", default="No incident summary supplied.")
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--replace", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repo = args.repo.resolve(strict=True)
        runtime_root = args.runtime_root.resolve()
        inputs = Inputs(
            repo=repo,
            runtime_root=runtime_root,
            private_service_url=validate_url(
                "private service URL", args.private_service_url
            ),
            analyst_service_url=validate_url(
                "analyst service URL", args.analyst_service_url
            ),
            model=validate_setting("model", args.model),
            provider=validate_setting("provider", args.provider),
            incident_summary=validate_setting(
                "incident summary", args.incident_summary
            ),
            dry_run=args.dry_run,
            replace=args.replace,
        )
        if not inputs.dry_run:
            inputs.runtime_root.mkdir(parents=True, exist_ok=True)
        reports = [reconcile_profile(inputs, profile) for profile in PROFILES]
    except (OSError, ReconciliationError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}), file=sys.stderr)
        return 2
    report = {
        "schema_version": 1,
        "status": "dry-run" if args.dry_run else "ok",
        "generated_at": timestamp(),
        "repo": str(inputs.repo),
        "runtime_root": str(inputs.runtime_root),
        "profiles": reports,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
