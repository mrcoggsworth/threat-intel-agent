#!/usr/bin/env python3
"""Create and verify secret-free, hash-chained deployment receipts."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def verify_receipt(receipt: dict[str, Any]) -> bool:
    """Verify the receipt's content hash without trusting its stored hash."""

    stored = receipt.get("receipt_hash")
    if not isinstance(stored, str):
        return False
    unsigned = dict(receipt)
    del unsigned["receipt_hash"]
    return hashlib.sha256(_canonical(unsigned)).hexdigest() == stored


def verify_receipt_file(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and verify_receipt(value)


def create_receipt(
    path: Path,
    *,
    artifact_reference: str,
    artifact_digest: str,
    source_revision: str,
    migration_revision: str,
    environment_checksum: str,
    approval_reference: str,
    approval_identity: str,
    rollback_image: str,
    rollback_receipt: str,
    backup_metadata: str,
    health_endpoint: str,
    health_verified_at: str,
    result: str = "succeeded",
) -> dict[str, Any]:
    """Write one new receipt without overwriting an existing receipt."""

    if path.exists():
        raise FileExistsError(f"receipt already exists: {path}")
    previous_hash = None
    previous_path = path.parent / "latest.receipt.json"
    if previous_path.is_file():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict) or not verify_receipt(previous):
            raise ValueError(f"previous receipt is not verifiable: {previous_path}")
        value = previous.get("receipt_hash")
        previous_hash = value if isinstance(value, str) else None

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "result": result,
        "artifact": {
            "reference": artifact_reference,
            "digest": artifact_digest,
            "source_revision": source_revision,
        },
        "migration": {"revision": migration_revision, "status": "applied"},
        "environment_checksum": environment_checksum,
        "backup": {"metadata": backup_metadata, "ready": True},
        "health": {"endpoint": health_endpoint, "verified_at": health_verified_at},
        "approval": {
            "reference": approval_reference,
            "identity": approval_identity,
        },
        "rollback": {"image": rollback_image, "receipt": rollback_receipt},
        "previous_receipt_hash": previous_hash,
    }
    receipt["receipt_hash"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        with contextlib.suppress(OSError):
            path.unlink()
        raise
    latest = path.parent / "latest.receipt.json"
    latest.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def _create_from_environment() -> None:
    create_receipt(
        Path(os.environ["HERMES_RECEIPT_PATH"]),
        artifact_reference=os.environ["HERMES_ARTIFACT_REFERENCE"],
        artifact_digest=os.environ["HERMES_ARTIFACT_DIGEST"],
        source_revision=os.environ["HERMES_SOURCE_REVISION"],
        migration_revision=os.environ["HERMES_MIGRATION_REVISION"],
        environment_checksum=os.environ["HERMES_ENVIRONMENT_CHECKSUM"],
        approval_reference=os.environ["HERMES_APPROVAL_REFERENCE"],
        approval_identity=os.environ["HERMES_APPROVAL_IDENTITY"],
        rollback_image=os.environ["HERMES_ROLLBACK_IMAGE"],
        rollback_receipt=os.environ["HERMES_ROLLBACK_RECEIPT"],
        backup_metadata=os.environ["HERMES_BACKUP_METADATA"],
        health_endpoint=os.environ["HERMES_HEALTH_ENDPOINT"],
        health_verified_at=os.environ["HERMES_HEALTH_VERIFIED_AT"],
        result=os.environ.get("HERMES_DEPLOYMENT_RESULT", "succeeded"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify is not None:
        print("verified" if verify_receipt_file(args.verify) else "invalid")
        raise SystemExit(0 if verify_receipt_file(args.verify) else 1)
    _create_from_environment()
