# ruff: noqa: B008
"""CLI commands for CTI analyst bundle pre-flight validation and diagnostics."""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import typer
from pydantic import ValidationError

from hermes_cti.core.settings import load_settings
from hermes_cti.reporting.contracts import ReportBundle
from hermes_cti.reporting.validation import ReportValidator

analyst_app = typer.Typer(
    help=(
        "Analyst bundle pre-flight validation, sequence allocation, "
        "and health diagnostics."
    )
)

DEFAULT_ANALYST_URL = "https://matrix-1.taild27e3c.ts.net:9443"
TOKEN_PATHS = (
    Path("/etc/hermes/cti-analyst/service-token"),
    Path.home() / ".local/state/cti-hermes/secrets/analyst-token",
    Path.home() / "matrix-cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token",
)
DB_SECRET_PATHS = (
    Path.home() / ".local/state/cti-hermes/secrets/database-url",
    Path.home() / "matrix-cptcoggsworth/.local/state/cti-hermes/secrets/database-url",
)


def _load_token(explicit_token_path: Path | None = None) -> str | None:
    env_token = os.environ.get("HERMES_ANALYST_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    env_token_file = os.environ.get("HERMES_ANALYST_SERVICE_TOKEN_FILE")
    if env_token_file and (token := _read_token_file(Path(env_token_file))):
        return token

    search_paths = [explicit_token_path] if explicit_token_path else []
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        search_paths.append(Path(hermes_home) / "credentials/service-token")
    search_paths.extend(TOKEN_PATHS)
    for path in search_paths:
        if token := _read_token_file(path):
            return token
    return None


def _read_token_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content or None
    except OSError:
        return None


def _load_db_url() -> str | None:
    for path in DB_SECRET_PATHS:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except OSError:
                continue
    return None


@analyst_app.command("validate-bundle")
def validate_bundle(
    bundle_path: Path = typer.Argument(
        ...,
        help="Path to JSON file containing ReportBundle (or '-' for stdin).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display full bundle metadata."
    ),
) -> None:
    """Validate a ReportBundle offline against schema and detection rules."""
    if str(bundle_path) == "-":
        raw_content = sys.stdin.read()
    else:
        if not bundle_path.is_file():
            typer.echo(f"Error: file not found: {bundle_path}", err=True)
            raise typer.Exit(code=1)
        raw_content = bundle_path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        typer.echo(f"[FAILED] Invalid JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # 1. Pydantic schema validation
    try:
        bundle = ReportBundle.model_validate(data)
    except ValidationError as exc:
        typer.echo(
            f"[FAILED] Schema validation failed with {len(exc.errors())} error(s):",
            err=True,
        )
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "invalid")
            typer.echo(f"  - {loc}: {msg}", err=True)
        raise typer.Exit(code=1) from exc

    # 2. Evidence coverage validation
    validator = ReportValidator()
    coverage = validator.validate_coverage(bundle)
    if not coverage.valid:
        typer.echo("[FAILED] Evidence coverage validation failed:", err=True)
        if coverage.missing_sections:
            missing_secs = [s.value for s in coverage.missing_sections]
            typer.echo(
                f"  Missing required sections: {missing_secs}",
                err=True,
            )
        if coverage.unsupported_claims:
            typer.echo(
                "  Unsupported claims (words in headline missing from evidence "
                "or forbidden internal claims):",
                err=True,
            )
            for claim in coverage.unsupported_claims:
                typer.echo(f"    * '{claim}'", err=True)
        if coverage.unsupported_remediation:
            typer.echo("  Unsupported remediation actions:", err=True)
            for rem in coverage.unsupported_remediation:
                typer.echo(f"    * {rem}", err=True)
        raise typer.Exit(code=1)

    # 3. Detection and compilation validation
    try:
        validator.validate(bundle)
    except Exception as exc:
        typer.echo(f"[FAILED] Detection or rule validation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("[SUCCESS] ReportBundle passed all schema and publication gates!")
    typer.echo(f"  Headline:     {bundle.headline}")
    typer.echo(f"  Public ID:    {bundle.public_id or '(none assigned)'}")
    typer.echo(f"  Slug:         {bundle.slug}")
    sev = (
        bundle.severity.value if hasattr(bundle.severity, "value") else bundle.severity
    )
    typer.echo(f"  Severity:     {sev}")
    typer.echo(f"  Evidence:     {len(bundle.evidence)} items")
    typer.echo(f"  IOCs:         {len(bundle.iocs)} items")
    typer.echo(f"  CVEs:         {len(bundle.vulnerabilities)} items")
    typer.echo(f"  ATT&CK:       {len(bundle.attack_mappings)} mappings")
    typer.echo(f"  Detections:   {len(bundle.detections)} artifacts")
    hunt_desc = (
        f"Present ({len(bundle.hunt.execution_phases)} phases)"
        if bundle.hunt
        else "None"
    )
    typer.echo(f"  Hunt:         {hunt_desc}")
    typer.echo(f"  Remediation:  {'Present' if bundle.remediation else 'None'}")


@analyst_app.command("next-public-id")
def next_public_id(
    year: int = typer.Option(
        datetime.now(UTC).year,
        "--year",
        help="Report release year (default: current year).",
    ),
    analyst_url: str = typer.Option(
        DEFAULT_ANALYST_URL,
        "--api-url",
        help="Analyst API base URL.",
    ),
    token_file: Path | None = typer.Option(
        None,
        "--token-file",
        help="Path to analyst service token file.",
    ),
) -> None:
    """Determine the next sequential public report identifier (e.g. PUB-2026-019)."""
    highest_seq = 0
    prefix = f"PUB-{year}-"

    # Strategy 1: Attempt direct PostgreSQL query if DB credentials exist
    db_url = _load_db_url()
    try:
        import asyncio

        from pydantic import SecretStr
        from sqlalchemy import select

        from hermes_cti.db.models import Report
        from hermes_cti.db.session import Database

        async def _query_db() -> list[str]:
            settings = load_settings()
            if db_url and not settings.database_url:
                settings = settings.model_copy(
                    update={"database_url": SecretStr(db_url)}
                )
            db = Database(settings)
            async with db.session() as session:
                stmt = select(Report.public_id).where(
                    Report.public_id.like(f"{prefix}%")
                )
                res = await session.execute(stmt)
                return [row[0] for row in res.all()]

        ids = asyncio.run(asyncio.wait_for(_query_db(), timeout=3.0))
        for pub_id in ids:
            match = re.match(rf"^PUB-{year}-(\d{{3}})$", pub_id)
            if match:
                highest_seq = max(highest_seq, int(match.group(1)))
    except Exception:
        pass

    # Strategy 2: Query public portal reports API /api/v1/public/reports
    if highest_seq == 0:
        ctx = ssl._create_unverified_context()
        page = 1
        base = analyst_url.rstrip("/")
        while page <= 5:
            url = f"{base}/api/v1/public/reports?page={page}&page_size=100"
            try:
                req = urllib.request.Request(
                    url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    items = payload.get("items", [])
                    if not items:
                        break
                    for item in items:
                        pid = item.get("public_id", "")
                        match = re.match(rf"^PUB-{year}-(\d{{3}})$", pid)
                        if match:
                            highest_seq = max(highest_seq, int(match.group(1)))
                    if len(items) < 100:
                        break
                    page += 1
            except Exception:
                break

    next_seq = highest_seq + 1
    next_id = f"PUB-{year}-{next_seq:03d}"
    typer.echo(next_id)


@analyst_app.command("health")
def health(
    analyst_url: str = typer.Option(
        DEFAULT_ANALYST_URL,
        "--api-url",
        help="Analyst API base URL.",
    ),
    token_file: Path | None = typer.Option(
        None,
        "--token-file",
        help="Path to analyst service token file.",
    ),
    cron_dir: Path | None = typer.Option(
        None,
        "--cron-dir",
        help="Profile cron directory to inspect for locks.",
    ),
) -> None:
    """Diagnose analyst API connectivity, credentials, and cron lock status."""
    typer.echo("CTI-Hermes Analyst Health Diagnosis:")
    typer.echo(f"  Target Endpoint: {analyst_url}")

    # 1. Credentials inspection
    token = _load_token(token_file)
    if token:
        masked = token[:4] + "..." + token[-4:] if len(token) >= 8 else "***"
        typer.echo(f"  [OK] Service Token found ({masked})")
    else:
        typer.echo(
            "  [WARNING] Service Token NOT found in standard paths "
            "or HERMES_ANALYST_TOKEN"
        )

    # 2. Connectivity and public liveness
    ctx = ssl._create_unverified_context()
    live_url = f"{analyst_url.rstrip('/')}/health/live"
    try:
        req = urllib.request.Request(live_url)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            typer.echo(f"  [OK] Public Liveness: HTTP {resp.status}")
    except Exception as exc:
        typer.echo(f"  [FAIL] Public Liveness unreachable: {exc}")

    # 3. Authenticated endpoint inspection
    if token:
        status_url = f"{analyst_url.rstrip('/')}/api/v1/analyst/status"
        try:
            req = urllib.request.Request(
                status_url,
                headers={"X-Analyst-Token": token, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                typer.echo(
                    f"  [OK] Authenticated Analyst API reachable (HTTP {resp.status})"
                )
                if "application_version" in data:
                    typer.echo(f"       App Version: {data.get('application_version')}")
                if "readiness" in data:
                    typer.echo(f"       Readiness: {data.get('readiness')}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                typer.echo(
                    "  [FAIL] Analyst API returned HTTP 404 "
                    "(Endpoint may require authentication or invalid token)"
                )
            else:
                typer.echo(
                    f"  [FAIL] Analyst API returned HTTP {exc.code}: {exc.reason}"
                )
        except Exception as exc:
            typer.echo(f"  [FAIL] Analyst API connection error: {exc}")

    # 4. Lock inspection
    target_cron = cron_dir or (Path.home() / ".hermes/profiles/cti-analyst/cron")
    if target_cron.is_dir():
        locks = list(target_cron.glob(".*.lock")) + list(target_cron.glob("*.lock"))
        typer.echo(f"  Lock Status in {target_cron}:")
        now = datetime.now(UTC).timestamp()
        stale_count = 0
        for lf in locks:
            age = int(now - lf.stat().st_mtime)
            is_stale = age > 900 and lf.name not in {".tick.lock", "auth.lock"}
            status_tag = "[STALE]" if is_stale else "[ACTIVE]"
            if is_stale:
                stale_count += 1
            typer.echo(f"    - {status_tag} {lf.name} (age: {age}s)")
        if not locks:
            typer.echo("    - No locks currently held.")
        if stale_count > 0:
            typer.echo(
                f"    [ACTION REQUIRED] {stale_count} stale lock(s) detected. "
                "Run scripts/clean-hermes-locks.sh to clear."
            )
