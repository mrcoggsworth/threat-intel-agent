#!/usr/bin/env python3
"""Evidence gate for maintainer recovery jobs.

The gate is deliberately independent of the recovery action. A caller must
acquire the gate before doing work and complete it afterward. Healthy or
unknown monitor results never acquire the recovery lock.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

ACTIONABLE_STATES = frozenset({"actionable_failure", "operator_required"})


def _now() -> datetime:
    return datetime.now(UTC)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class RecoveryDecision:
    allowed: bool
    reason: str
    event_id: str
    monitor_state: str
    run_id: str | None
    correlation_id: str | None


class RecoveryGate:
    """Coordinate one evidence-backed recovery attempt at a time."""

    def __init__(
        self,
        state_dir: Path,
        *,
        cooldown: timedelta = timedelta(minutes=30),
        now: datetime | None = None,
    ) -> None:
        self.state_dir = state_dir
        self.cooldown = cooldown
        self.now = now or _now()
        self.lock_path = state_dir / "recovery.lock"
        self.state_path = state_dir / "recovery-state.json"
        self.audit_path = state_dir / "recovery-events.jsonl"
        self._event_id: str | None = None

    def _audit(self, event: str, decision: RecoveryDecision, **extra: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "event_id": decision.event_id,
            "event": event,
            "recorded_at": self.now.isoformat(),
            "monitor_state": decision.monitor_state,
            "reason": decision.reason,
            "run_id": decision.run_id,
            "correlation_id": decision.correlation_id,
            **extra,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def evaluate(self, evidence_path: Path) -> RecoveryDecision:
        evidence = _read_json(evidence_path)
        monitor_state = str(evidence.get("state", "unknown"))
        event_id = str(evidence.get("event_id") or uuid4())
        run_id = evidence.get("run_id")
        correlation_id = evidence.get("correlation_id")
        decision = RecoveryDecision(
            allowed=False,
            reason="monitor evidence is not actionable",
            event_id=event_id,
            monitor_state=monitor_state,
            run_id=run_id if isinstance(run_id, str) else None,
            correlation_id=(
                correlation_id if isinstance(correlation_id, str) else None
            ),
        )
        if monitor_state not in ACTIONABLE_STATES:
            self._audit("suppressed", decision)
            return decision

        previous = _read_json(self.state_path)
        last_attempt = previous.get("last_attempt_at")
        if isinstance(last_attempt, str):
            try:
                elapsed = self.now - datetime.fromisoformat(last_attempt)
            except ValueError:
                elapsed = self.cooldown
            if elapsed < self.cooldown:
                decision = RecoveryDecision(
                    allowed=False,
                    reason="recovery cooldown is active",
                    event_id=event_id,
                    monitor_state=monitor_state,
                    run_id=decision.run_id,
                    correlation_id=decision.correlation_id,
                )
                self._audit("suppressed", decision)
                return decision

        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.lock_path.mkdir()
        except FileExistsError:
            decision = RecoveryDecision(
                allowed=False,
                reason="another recovery is already in progress",
                event_id=event_id,
                monitor_state=monitor_state,
                run_id=decision.run_id,
                correlation_id=decision.correlation_id,
            )
            self._audit("suppressed", decision)
            return decision

        self._event_id = event_id
        self.state_path.write_text(
            json.dumps(
                {
                    "last_attempt_at": self.now.isoformat(),
                    "event_id": event_id,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        decision = RecoveryDecision(
            allowed=True,
            reason="actionable monitor evidence acquired",
            event_id=event_id,
            monitor_state=monitor_state,
            run_id=decision.run_id,
            correlation_id=decision.correlation_id,
        )
        self._audit("attempted", decision)
        return decision

    def complete(self, decision: RecoveryDecision, *, outcome: str) -> None:
        if self._event_id != decision.event_id:
            raise ValueError("recovery decision does not own this gate")
        if not outcome or outcome not in {"completed", "failed", "suppressed"}:
            raise ValueError("outcome must be completed, failed, or suppressed")
        self._audit("completed", decision, outcome=outcome)
        with contextlib.suppress(OSError):
            self.lock_path.rmdir()
        self._event_id = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(os.environ.get("HERMES_RECOVERY_STATE_DIR", "/runtime")),
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=int(os.environ.get("HERMES_RECOVERY_COOLDOWN_SECONDS", "1800")),
    )
    args = parser.parse_args()
    gate = RecoveryGate(
        args.state_dir, cooldown=timedelta(seconds=args.cooldown_seconds)
    )
    decision = gate.evaluate(args.evidence)
    print(json.dumps(asdict(decision), sort_keys=True))
    return 0 if decision.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
